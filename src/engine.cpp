#include "market_ledger/engine.hpp"

#include <algorithm>
#include <cctype>
#include <istream>
#include <ostream>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace market_ledger {
namespace {
bool token(const std::string& value) {
    return !value.empty() && value.size() <= 64 &&
        std::all_of(value.begin(), value.end(), [](unsigned char ch) {
            return (ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z') ||
                   (ch >= '0' && ch <= '9') || ch == '_' || ch == '-' || ch == '.';
        });
}
void require_token(const std::string& value, const std::string& label) {
    if (!token(value)) throw std::runtime_error(label + ": use 1-64 ASCII letters, digits, _, - or .");
}
std::vector<std::string> split(const std::string& line, char delimiter) {
    std::vector<std::string> fields;
    std::size_t start = 0;
    for (;;) {
        const auto end = line.find(delimiter, start);
        fields.push_back(line.substr(start, end == std::string::npos ? end : end - start));
        if (end == std::string::npos) break;
        start = end + 1;
    }
    return fields;
}
template<class Callback>
void read_csv(std::istream& input, const std::string& header, Callback callback) {
    std::string line;
    std::size_t line_number = 0, count = 0;
    bool found_header = false;
    while (std::getline(input, line)) {
        ++line_number;
        if (line.size() > 4096) throw std::runtime_error("line exceeds 4096 bytes");
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty() || line.front() == '#') continue;
        if (!found_header) {
            if (line != header) throw std::runtime_error("CSV header must be: " + header);
            found_header = true;
            continue;
        }
        if (++count > max_events) throw std::runtime_error("input exceeds 10000 events");
        try { callback(split(line, ',')); }
        catch (const std::exception& error) {
            throw std::runtime_error("line " + std::to_string(line_number) + ": " + error.what());
        }
    }
    if (input.bad()) throw std::runtime_error("failed to read input");
    if (!found_header) throw std::runtime_error("missing CSV header");
}
void check_order(const Order& order) {
    require_token(order.id, "id");
    require_token(order.broker, "broker");
    if (canonical_instrument(order.instrument) != order.instrument)
        throw std::runtime_error("instrument must be canonical");
    if (order.side != "BUY" && order.side != "SELL") throw std::runtime_error("side must be BUY or SELL");
    if (order.time < 0 || order.time > max_time || order.price < 1 || order.price > max_price ||
        order.quantity < 1 || order.quantity > max_quantity || order.ttl < -1 || order.ttl > max_time)
        throw std::runtime_error("order outside supported limits");
}
} // namespace

Number integer(const std::string& value, Number minimum, Number maximum, const std::string& label) {
    if (value.empty()) throw std::runtime_error(label + ": missing integer");
    const std::size_t start = value.front() == '-' ? 1 : 0;
    if (start == value.size() || !std::all_of(value.begin() + static_cast<std::ptrdiff_t>(start),
        value.end(), [](unsigned char ch) { return ch >= '0' && ch <= '9'; }))
        throw std::runtime_error(label + ": expected integer");
    Number result;
    try { result = std::stoll(value); }
    catch (const std::exception&) { throw std::runtime_error(label + ": integer out of range"); }
    if (result < minimum || result > maximum) throw std::runtime_error(label + ": integer out of range");
    return result;
}

std::string canonical_instrument(const std::string& value) {
    if (value.size() > 2048) throw std::runtime_error("instrument too long");
    if (value.find(':') == std::string::npos && value.find('|') == std::string::npos) {
        require_token(value, "instrument");
        return value;
    }
    const auto legs = split(value, '|');
    if (legs.size() > 16) throw std::runtime_error("basket exceeds 16 legs");
    std::map<std::string, Number> coefficients;
    for (const auto& leg : legs) {
        const auto pair = split(leg, ':');
        if (pair.size() != 2) throw std::runtime_error("basket legs must be SYMBOL:coefficient");
        require_token(pair[0], "basket symbol");
        coefficients[pair[0]] += integer(pair[1], -max_quantity, max_quantity, "coefficient");
    }
    for (auto it = coefficients.begin(); it != coefficients.end();) {
        if (it->second == 0) it = coefficients.erase(it);
        else {
            if (it->second < -max_quantity || it->second > max_quantity)
                throw std::runtime_error("combined basket coefficient out of range");
            ++it;
        }
    }
    std::string result;
    for (const auto& leg : coefficients) {
        if (leg.second == 0) continue;
        if (!result.empty()) result += '|';
        result += leg.first + ':' + std::to_string(leg.second);
    }
    if (result.empty()) throw std::runtime_error("basket has zero exposure");
    // A unit basket and its single-symbol representation describe the same instrument.
    if (coefficients.size() == 1 && coefficients.begin()->second == 1) return coefficients.begin()->first;
    return result;
}

std::vector<Order> read_orders(std::istream& input) {
    std::vector<Order> orders;
    read_csv(input, "timestamp,id,broker,instrument,side,price,quantity,ttl", [&](const auto& f) {
        if (f.size() != 8) throw std::runtime_error("expected 8 columns");
        Order order;
        order.time = integer(f[0], 0, max_time, "timestamp");
        order.id = f[1]; order.broker = f[2]; order.instrument = canonical_instrument(f[3]);
        order.side = f[4]; order.price = integer(f[5], 1, max_price, "price");
        order.quantity = integer(f[6], 1, max_quantity, "quantity");
        order.ttl = integer(f[7], -1, max_time, "ttl");
        check_order(order);
        if (!orders.empty() && order.time < orders.back().time)
            throw std::runtime_error("timestamps must be nondecreasing");
        orders.push_back(std::move(order));
    });
    return orders;
}

void Engine::expire(Number time) {
    while (!expiry_.empty() && expiry_.top().time < time) {
        if (active_.erase(expiry_.top().id)) ++result_.expired;
        expiry_.pop();
    }
}

template<class Levels> void Engine::match(Order& incoming, Levels& levels) {
    while (incoming.quantity > 0 && !levels.empty()) {
        auto level = levels.begin();
        if ((incoming.side == "BUY" && level->first > incoming.price) ||
            (incoming.side == "SELL" && level->first < incoming.price)) break;
        auto& queue = level->second;
        while (!queue.empty() && incoming.quantity > 0) {
            auto found = active_.find(queue.front());
            if (found == active_.end()) { queue.pop_front(); continue; }
            auto& resting = found->second;
            if (resting.order.broker == incoming.broker) {
                // Cancel the arriving remainder instead of trading against its owner.
                ++result_.self_prevented;
                incoming.quantity = 0;
                break;
            }
            const auto quantity = std::min(incoming.quantity, resting.remaining);
            const auto& buy = incoming.side == "BUY" ? incoming : resting.order;
            const auto& sell = incoming.side == "SELL" ? incoming : resting.order;
            result_.trades.push_back({incoming.time, resting.order.price, quantity,
                incoming.instrument, buy.id, sell.id, buy.broker, sell.broker});
            const Number value = resting.order.price * quantity;
            result_.units += quantity; result_.turnover += value;
            auto& buyer = result_.balances[buy.broker];
            auto& seller = result_.balances[sell.broker];
            buyer.bought += quantity; buyer.cash -= value;
            seller.sold += quantity; seller.cash += value;
            incoming.quantity -= quantity; resting.remaining -= quantity;
            if (!resting.remaining) { active_.erase(found); queue.pop_front(); }
        }
        if (queue.empty()) levels.erase(level);
    }
}

void Engine::submit(const Order& order) {
    check_order(order);
    if (result_.submitted >= static_cast<Number>(max_events)) throw std::runtime_error("input exceeds 10000 events");
    if (order.time < last_time_) throw std::runtime_error("timestamps must be nondecreasing");
    if (!seen_.insert(order.id).second) throw std::runtime_error("duplicate order id: " + order.id);
    last_time_ = order.time;
    expire(order.time);
    ++result_.submitted;
    result_.balances[order.broker];
    auto incoming = order;
    auto& book = books_[order.instrument];
    if (order.side == "BUY") match(incoming, book.asks);
    else match(incoming, book.bids);
    if (incoming.quantity > 0) {
        active_.emplace(order.id, Resting{order, incoming.quantity});
        if (order.side == "BUY") book.bids[order.price].push_back(order.id);
        else book.asks[order.price].push_back(order.id);
        if (order.ttl >= 0) expiry_.push({order.time + order.ttl, order.id});
    }
}

Summary Engine::summary() const {
    auto copy = result_;
    copy.resting = static_cast<Number>(active_.size());
    return copy;
}

std::vector<Quote> read_quotes(std::istream& input) {
    std::vector<Quote> quotes;
    read_csv(input, "timestamp,venue,instrument,bid,ask,bid_size,ask_size", [&](const auto& f) {
        if (f.size() != 7) throw std::runtime_error("expected 7 columns");
        Quote quote;
        quote.time = integer(f[0], 0, max_time, "timestamp");
        require_token(f[1], "venue"); quote.venue = f[1];
        quote.instrument = canonical_instrument(f[2]);
        quote.bid = integer(f[3], 1, max_price, "bid");
        quote.ask = integer(f[4], 1, max_price, "ask");
        quote.bid_size = integer(f[5], 0, max_quantity, "bid_size");
        quote.ask_size = integer(f[6], 0, max_quantity, "ask_size");
        if (quote.bid > quote.ask) throw std::runtime_error("venue bid exceeds ask");
        if (!quotes.empty() && quote.time < quotes.back().time)
            throw std::runtime_error("timestamps must be nondecreasing");
        quotes.push_back(std::move(quote));
    });
    return quotes;
}

std::vector<Opportunity> scan(const std::vector<Quote>& quotes, Number fee, Number max_age, Number cap) {
    if (fee < 0 || fee > max_price || max_age < 0 || max_age > max_time || cap < 1 || cap > max_quantity)
        throw std::runtime_error("scanner options outside supported limits");
    // Each row replaces both sides of the venue's previous quote.
    std::map<std::string, std::map<std::string, Quote>> latest;
    Number now = 0;
    for (const auto& quote : quotes) {
        latest[quote.instrument][quote.venue] = quote;
        now = quote.time;
    }
    std::vector<Opportunity> opportunities;
    for (const auto& instrument : latest) {
        Opportunity best{};
        // One best route per instrument; independent routes are never added as a portfolio return.
        for (const auto& buy : instrument.second) for (const auto& sell : instrument.second) {
            if (buy.first == sell.first || now - buy.second.time > max_age || now - sell.second.time > max_age) continue;
            const Number quantity = std::min({buy.second.ask_size, sell.second.bid_size, cap});
            const Number edge = sell.second.bid - buy.second.ask - 2 * fee;
            const Number profit = edge * quantity;
            if (quantity > 0 && edge > 0 && profit > best.net_profit)
                best = {instrument.first, buy.first, sell.first, buy.second.ask, sell.second.bid,
                        quantity, edge, profit};
        }
        if (best.net_profit > 0) opportunities.push_back(best);
    }
    return opportunities;
}

void write_summary(std::ostream& out, const Summary& s) {
    out << "{\"version\":\"1.0.0\",\"mode\":\"simulation\",\"submitted_orders\":" << s.submitted
        << ",\"trade_count\":" << s.trades.size() << ",\"units_traded\":" << s.units
        << ",\"turnover_cents\":" << s.turnover << ",\"expired_orders\":" << s.expired
        << ",\"self_trade_preventions\":" << s.self_prevented << ",\"resting_orders\":" << s.resting
        << ",\"trades\":[";
    bool first = true;
    for (const auto& t : s.trades) {
        if (!first) out << ',';
        first = false;
        out << "{\"timestamp\":" << t.time << ",\"instrument\":\"" << t.instrument
            << "\",\"buy_order\":\"" << t.buy_order << "\",\"sell_order\":\"" << t.sell_order
            << "\",\"buyer\":\"" << t.buyer << "\",\"seller\":\"" << t.seller
            << "\",\"price_cents\":" << t.price << ",\"quantity\":" << t.quantity << '}';
    }
    out << "],\"brokers\":["; first = true;
    for (const auto& pair : s.balances) {
        if (!first) out << ',';
        first = false;
        out << "{\"broker\":\"" << pair.first << "\",\"bought\":" << pair.second.bought
            << ",\"sold\":" << pair.second.sold << ",\"net_cash_cents\":" << pair.second.cash << '}';
    }
    out << "]}\n";
}
void write_opportunities(std::ostream& out, const std::vector<Opportunity>& opportunities) {
    out << "{\"version\":\"1.0.0\",\"mode\":\"snapshot_analysis\",\"opportunities\":[";
    bool first = true;
    for (const auto& o : opportunities) {
        if (!first) out << ',';
        first = false;
        out << "{\"instrument\":\"" << o.instrument << "\",\"buy_venue\":\"" << o.buy_venue
            << "\",\"sell_venue\":\"" << o.sell_venue << "\",\"buy_price_cents\":" << o.buy_price
            << ",\"sell_price_cents\":" << o.sell_price << ",\"quantity\":" << o.quantity
            << ",\"net_per_unit_cents\":" << o.net_per_unit << ",\"potential_profit_cents\":" << o.net_profit << '}';
    }
    out << "]}\n";
}
} // namespace market_ledger
