#pragma once

#include <cstdint>
#include <deque>
#include <functional>
#include <iosfwd>
#include <map>
#include <queue>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace market_ledger {
using Number = std::int64_t;
constexpr Number max_price = 100000000;
constexpr Number max_quantity = 1000000;
constexpr Number max_time = 1000000000000LL;
constexpr std::size_t max_events = 10000;

struct Order {
    Number time = 0;
    std::string id, broker, instrument, side;
    Number price = 0, quantity = 0, ttl = -1;
};
struct Trade {
    Number time, price, quantity;
    std::string instrument, buy_order, sell_order, buyer, seller;
};
struct Balance { Number bought = 0, sold = 0, cash = 0; };
struct Summary {
    Number submitted = 0, expired = 0, self_prevented = 0;
    Number units = 0, turnover = 0, resting = 0;
    std::vector<Trade> trades;
    std::map<std::string, Balance> balances;
};

class Engine {
public:
    void submit(const Order& order);
    Summary summary() const;
private:
    using Level = std::deque<std::string>;
    struct Book {
        std::map<Number, Level, std::greater<Number>> bids;
        std::map<Number, Level> asks;
    };
    struct Resting { Order order; Number remaining; };
    struct Expiry {
        Number time;
        std::string id;
        bool operator>(const Expiry& other) const { return time > other.time; }
    };
    template<class Levels> void match(Order& incoming, Levels& levels);
    void expire(Number time);
    Number last_time_ = 0;
    Summary result_;
    std::map<std::string, Book> books_;
    std::unordered_map<std::string, Resting> active_;
    std::unordered_set<std::string> seen_;
    std::priority_queue<Expiry, std::vector<Expiry>, std::greater<Expiry>> expiry_;
};

struct Quote {
    Number time = 0;
    std::string venue, instrument;
    Number bid = 0, ask = 0, bid_size = 0, ask_size = 0;
};
struct Opportunity {
    std::string instrument, buy_venue, sell_venue;
    Number buy_price, sell_price, quantity, net_per_unit, net_profit;
};
std::vector<Order> read_orders(std::istream& input);
std::vector<Quote> read_quotes(std::istream& input);
std::vector<Opportunity> scan(const std::vector<Quote>& quotes, Number fee,
                              Number max_age, Number quantity_cap);
Number integer(const std::string& value, Number minimum, Number maximum,
               const std::string& label);
std::string canonical_instrument(const std::string& value);
void write_summary(std::ostream& output, const Summary& summary);
void write_opportunities(std::ostream& output, const std::vector<Opportunity>& opportunities);
} // namespace market_ledger
