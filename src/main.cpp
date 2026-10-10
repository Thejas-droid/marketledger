#include "market_ledger/engine.hpp"

#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>

namespace {
const char* help =
    "Market Ledger 1.0.0 | local trading simulator\n"
    "Usage:\n"
    "  market_ledger simulate --input orders.csv [--output report.json]\n"
    "  market_ledger arbitrage --input quotes.csv [--fee 0] [--max-age 5] [--max-quantity 1000]\n"
    "                      [--output report.json]\n"
    "  market_ledger --version\n"
    "Prices and fees are integer cents; timestamps and max-age use the input's time unit.\n";
}
int main(int argc, char** argv) {
    try {
        if (argc == 1 || (argc == 2 && std::string(argv[1]) == "--help")) {
            std::cout << help; return 0;
        }
        const std::string command = argv[1];
        if (command == "--version" && argc == 2) { std::cout << "Market Ledger 1.0.0\n"; return 0; }
        if (command != "simulate" && command != "arbitrage") throw std::runtime_error("unknown command; use --help");
        std::map<std::string, std::string> options;
        for (int i = 2; i < argc; i += 2) {
            const std::string key = argv[i];
            const bool scanner_option = command == "arbitrage" &&
                (key == "--fee" || key == "--max-age" || key == "--max-quantity");
            if (key != "--input" && key != "--output" && !scanner_option)
                throw std::runtime_error("unknown option: " + key);
            if (i + 1 >= argc) throw std::runtime_error("missing value: " + key);
            if (!options.emplace(key, argv[i + 1]).second) throw std::runtime_error("duplicate option: " + key);
        }
        if (!options.count("--input")) throw std::runtime_error("--input is required");
        if (options.count("--output") && options.at("--output") == options.at("--input"))
            throw std::runtime_error("input and output must be different files");
        std::ifstream input(options.at("--input"));
        if (!input) throw std::runtime_error("cannot open input file");
        std::ostringstream report;
        if (command == "simulate") {
            const auto orders = market_ledger::read_orders(input);
            market_ledger::Engine engine;
            for (const auto& order : orders) engine.submit(order);
            market_ledger::write_summary(report, engine.summary());
        } else {
            const auto number = [&](const std::string& key, market_ledger::Number fallback,
                                    market_ledger::Number low, market_ledger::Number high) {
                return options.count(key) ? market_ledger::integer(options.at(key), low, high, key) : fallback;
            };
            const auto quotes = market_ledger::read_quotes(input);
            market_ledger::write_opportunities(report, market_ledger::scan(quotes,
                number("--fee", 0, 0, market_ledger::max_price),
                number("--max-age", 5, 0, market_ledger::max_time),
                number("--max-quantity", 1000, 1, market_ledger::max_quantity)));
        }
        if (options.count("--output")) {
            // Fail safely if a report already exists, including input aliases and symlinks.
            std::ifstream existing(options.at("--output"));
            if (existing) throw std::runtime_error("output file already exists; choose a new path");
            std::ofstream output(options.at("--output"));
            if (!output) throw std::runtime_error("cannot open output file");
            output << report.str();
            output.close();
            if (!output) throw std::runtime_error("failed to write output file");
        } else {
            std::cout << report.str();
            if (!std::cout) throw std::runtime_error("failed to write report");
        }
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
