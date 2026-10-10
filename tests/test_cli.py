"""Behavioral and randomized accounting tests against the compiled executable."""
import argparse
import json
from pathlib import Path
import random
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / "build/market-ledger"
ORDERS = "timestamp,id,broker,instrument,side,price,quantity,ttl\n"
QUOTES = "timestamp,venue,instrument,bid,ask,bid_size,ask_size\n"


class CLITests(unittest.TestCase):
    def run_input(self, rows, mode="simulate", options=(), valid=True, header=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            path.write_text((header if header is not None else ORDERS if mode == "simulate" else QUOTES) + rows,
                            encoding="utf-8")
            process = subprocess.run([str(BINARY), mode, "--input", str(path), *options],
                                     capture_output=True, text=True, timeout=15)
        if valid:
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertFalse(process.stderr)
            return json.loads(process.stdout)
        self.assertNotEqual(process.returncode, 0)
        self.assertFalse(process.stdout)
        self.assertIn("error:", process.stderr)
        return process.stderr

    def test_price_priority_partial_fill_and_resting_price(self):
        s = self.run_input("0,s1,A,X,SELL,105,4,-1\n0,s2,B,X,SELL,100,3,-1\n1,b1,C,X,BUY,110,5,-1\n")
        self.assertEqual([(t["sell_order"], t["price_cents"], t["quantity"]) for t in s["trades"]],
                         [("s2", 100, 3), ("s1", 105, 2)])
        self.assertEqual(s["turnover_cents"], 510)
        self.assertEqual(s["resting_orders"], 1)

    def test_buy_book_price_priority(self):
        s = self.run_input("0,b1,A,X,BUY,100,2,-1\n0,b2,B,X,BUY,110,2,-1\n1,s,C,X,SELL,90,3,-1\n")
        self.assertEqual([t["buy_order"] for t in s["trades"]], ["b2", "b1"])
        self.assertEqual(s["turnover_cents"], 320)

    def test_same_time_fifo_is_arrival_order(self):
        s = self.run_input("0,z,Z,X,SELL,100,1,-1\n0,a,A,X,SELL,100,1,-1\n0,b,B,X,BUY,100,2,-1\n")
        self.assertEqual([t["sell_order"] for t in s["trades"]], ["z", "a"])

    def test_expiration_is_inclusive(self):
        s = self.run_input("0,s,A,X,SELL,100,2,1\n1,b,B,X,BUY,100,1,-1\n2,c,C,X,BUY,100,1,-1\n")
        self.assertEqual(s["trade_count"], 1)
        self.assertEqual(s["expired_orders"], 1)
        self.assertEqual(s["resting_orders"], 1)

    def test_zero_ttl_only_matches_same_timestamp(self):
        s = self.run_input("0,s,A,X,SELL,100,2,0\n0,b,B,X,BUY,100,1,-1\n1,c,C,X,BUY,100,1,-1\n")
        self.assertEqual(s["units_traded"], 1)
        self.assertEqual(s["expired_orders"], 1)

    def test_filled_expiry_does_not_count_as_expired(self):
        s = self.run_input("0,s,A,X,SELL,100,1,0\n0,b,B,X,BUY,100,1,-1\n1,c,C,Y,BUY,100,1,-1\n")
        self.assertEqual(s["expired_orders"], 0)

    def test_self_trade_cancels_incoming_remainder(self):
        s = self.run_input("0,s1,B,X,SELL,90,1,-1\n0,s2,A,X,SELL,100,3,-1\n1,b,A,X,BUY,110,3,-1\n")
        self.assertEqual(s["units_traded"], 1)
        self.assertEqual(s["self_trade_preventions"], 1)
        self.assertEqual(s["resting_orders"], 1)

    def test_basket_normalization_and_zero_legs(self):
        s = self.run_input("0,s,A,Y:2|X:1,SELL,100,2,-1\n1,b,B,X:1|Y:1|Y:1,BUY,100,1,-1\n"
                           "2,c,A,Z:0|Q:1,SELL,50,1,-1\n3,d,B,Q,BUY,50,1,-1\n")
        self.assertEqual(s["trade_count"], 2)
        self.assertEqual(s["trades"][0]["instrument"], "X:1|Y:2")

    def test_different_baskets_do_not_match(self):
        s = self.run_input("0,s,A,X:1|Y:2,SELL,100,2,-1\n1,b,B,X:2|Y:1,BUY,100,2,-1\n")
        self.assertEqual(s["trade_count"], 0)

    def test_duplicate_id_rejected_even_after_fill(self):
        self.assertIn("duplicate order", self.run_input(
            "0,s,A,X,SELL,100,1,-1\n0,b,B,X,BUY,100,1,-1\n1,s,C,Y,SELL,100,1,-1\n", valid=False))

    def test_bad_orders_rejected(self):
        rows = ["0,s,A,X,SELL,0,1,-1", "0,s,A,X,SELL,100,0,-1", "0,s,A,X,SELL,100,1,-2",
                "0,s,A,X,OTHER,100,1,-1", "0,s,A,X,SELL,1.5,1,-1", "0,s,A,X,SELL,+1,1,-1",
                "0,s,A,X,SELL,9999999999999999999999,1,-1", "0,s,A,X,SELL,100,1,-1,extra",
                '0,s,A\"bad,X,SELL,100,1,-1', "0,s,A,X:1|X:-1,SELL,100,1,-1",
                "0,s,A,X:1000000|X:1,SELL,100,1,-1", "-1,s,A,X,SELL,100,1,-1"]
        for row in rows:
            with self.subTest(row=row):
                self.run_input(row + "\n", valid=False)

    def test_unsorted_timestamps(self):
        self.run_input("2,a,A,X,BUY,100,1,-1\n1,b,B,X,SELL,100,1,-1\n", valid=False)

    def test_empty_and_header_only(self):
        self.assertEqual(self.run_input("")["submitted_orders"], 0)
        self.run_input("", header="", valid=False)

    def test_crlf_and_comments(self):
        s = self.run_input("# comment\r\n0,s,A,X,SELL,100,1,-1\r\n\r\n", header=ORDERS.replace("\n", "\r\n"))
        self.assertEqual(s["submitted_orders"], 1)

    def test_arbitrage_fee_and_liquidity_cap(self):
        s = self.run_input("0,A,X,98,100,30,20\n0,B,X,110,112,8,20\n", "arbitrage",
                           ("--fee", "2", "--max-quantity", "5"))
        o = s["opportunities"][0]
        self.assertEqual((o["buy_venue"], o["sell_venue"], o["quantity"], o["potential_profit_cents"]),
                         ("A", "B", 5, 30))

    def test_no_edge_after_fees(self):
        s = self.run_input("0,A,X,98,100,20,20\n0,B,X,110,112,20,20\n", "arbitrage", ("--fee", "5"))
        self.assertEqual(s["opportunities"], [])

    def test_stale_quotes_and_update_replacement(self):
        s = self.run_input("0,A,X,98,100,20,20\n10,B,X,110,112,20,20\n", "arbitrage")
        self.assertEqual(s["opportunities"], [])
        s = self.run_input("0,A,X,98,100,20,20\n1,A,X,115,120,20,20\n1,B,X,110,112,20,20\n", "arbitrage")
        self.assertEqual(s["opportunities"][0]["buy_venue"], "B")

    def test_stale_boundary_is_inclusive(self):
        s = self.run_input("0,A,X,98,100,20,20\n5,B,X,110,112,20,20\n", "arbitrage")
        self.assertEqual(len(s["opportunities"]), 1)

    def test_zero_liquidity_no_route(self):
        s = self.run_input("0,A,X,98,100,20,0\n0,B,X,110,112,20,20\n", "arbitrage")
        self.assertEqual(s["opportunities"], [])

    def test_bad_quotes(self):
        for row in ["0,A,X,101,100,20,20", "0,A,X,98,100,-1,20", "0,A,X,0,100,20,20"]:
            with self.subTest(row=row):
                self.run_input(row + "\n", "arbitrage", valid=False)

    def test_best_route_is_by_total_profit(self):
        s = self.run_input("0,A,X,90,100,10,10\n0,B,X,120,125,1,10\n0,C,X,110,115,10,10\n", "arbitrage")
        self.assertEqual(s["opportunities"][0]["sell_venue"], "C")

    def test_maximum_values_remain_integer(self):
        s = self.run_input("0,s,A,X,SELL,100000000,1000000,-1\n0,b,B,X,BUY,100000000,1000000,-1\n")
        self.assertEqual(s["turnover_cents"], 100000000000000)

    def test_randomized_against_independent_reference(self):
        rng = random.Random(2026)
        for trial in range(20):
            orders, active, expected = [], [], []
            time = 0
            for i in range(100):
                time += rng.randrange(2)
                order = {"time": time, "id": f"o{i}", "broker": f"b{rng.randrange(5)}",
                         "instrument": rng.choice(["X", "Y"]), "side": rng.choice(["BUY", "SELL"]),
                         "price": rng.randrange(95, 106), "quantity": rng.randrange(1, 6),
                         "ttl": rng.choice([-1, 0, 2, 5])}
                orders.append(order.copy())
                active = [a for a in active if a["ttl"] == -1 or a["time"] + a["ttl"] >= time]
                candidates = [a for a in active if a["instrument"] == order["instrument"] and
                              a["side"] != order["side"] and
                              (a["price"] <= order["price"] if order["side"] == "BUY" else a["price"] >= order["price"])]
                candidates.sort(key=lambda a: (a["price"] if order["side"] == "BUY" else -a["price"],
                                               int(a["id"][1:])))
                for resting in candidates:
                    if order["quantity"] == 0:
                        break
                    if resting["broker"] == order["broker"]:
                        order["quantity"] = 0
                        break
                    qty = min(order["quantity"], resting["quantity"])
                    buy, sell = (order, resting) if order["side"] == "BUY" else (resting, order)
                    expected.append((time, buy["id"], sell["id"], resting["price"], qty))
                    order["quantity"] -= qty
                    resting["quantity"] -= qty
                    if resting["quantity"] == 0:
                        active.remove(resting)
                if order["quantity"]:
                    active.append(order)
            rows = "".join(f'{o["time"]},{o["id"]},{o["broker"]},{o["instrument"]},{o["side"]},'
                           f'{o["price"]},{o["quantity"]},{o["ttl"]}\n' for o in orders)
            with self.subTest(trial=trial):
                s = self.run_input(rows)
                actual = [(t["timestamp"], t["buy_order"], t["sell_order"], t["price_cents"], t["quantity"])
                          for t in s["trades"]]
                self.assertEqual(actual, expected)
                self.assertEqual(s["resting_orders"], len(active))
                self.assertEqual(sum(b["net_cash_cents"] for b in s["brokers"]), 0)
                self.assertEqual(sum(b["bought"] for b in s["brokers"]), s["units_traded"])
                self.assertEqual(sum(b["sold"] for b in s["brokers"]), s["units_traded"])

    def test_cli_errors(self):
        commands = [["unknown"], ["simulate"], ["simulate", "--input"],
                    ["simulate", "--input", "missing.csv"], ["simulate", "--fee", "1"],
                    ["simulate", "--input", "x", "--input", "y"]]
        for args in commands:
            with self.subTest(args=args):
                result = subprocess.run([str(BINARY), *args], capture_output=True, text=True, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(result.stdout)

    def test_report_file_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            command = [str(BINARY), "simulate", "--input", str(ROOT / "examples/orders.csv"), "--output", str(path)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            original = path.read_bytes()
            self.assertEqual(json.loads(original)["submitted_orders"], 12)
            result = subprocess.run(command, capture_output=True, text=True, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(path.read_bytes(), original)

    def test_bundled_golden_reports(self):
        for mode, filename, expected, options in [
            ("simulate", "orders.csv", "expected_simulation.json", []),
            ("arbitrage", "quotes.csv", "expected_arbitrage.json", ["--fee", "2"]),
        ]:
            with self.subTest(mode=mode):
                process = subprocess.run([str(BINARY), mode, "--input", str(ROOT / "examples" / filename), *options],
                                         capture_output=True, text=True, timeout=15)
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertEqual(json.loads(process.stdout),
                                 json.loads((ROOT / "examples" / expected).read_text(encoding="utf-8")))

    def test_event_limit(self):
        self.run_input("".join(f"0,o{i},A,X,BUY,100,1,-1\n" for i in range(10001)), valid=False)

    def test_line_size_and_scanner_option_limits(self):
        self.run_input("a" * 4097 + "\n", valid=False)
        for options in [("--fee", "-1"), ("--max-age", "-1"), ("--max-quantity", "0"),
                        ("--fee", "1.5"), ("--max-quantity", "1000001")]:
            with self.subTest(options=options):
                self.run_input("", "arbitrage", options, valid=False)

    def test_invalid_input_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "bad.csv", Path(directory) / "result.json"
            source.write_text(ORDERS + "0,s,A,X,SELL,0,1,-1\n", encoding="utf-8")
            process = subprocess.run([str(BINARY), "simulate", "--input", str(source), "--output", str(output)],
                                     capture_output=True, text=True, timeout=15)
            self.assertNotEqual(process.returncode, 0)
            self.assertFalse(output.exists())

    def test_expiry_at_maximum_timestamp(self):
        s = self.run_input("1000000000000,s,A,X,SELL,100,2,1000000000000\n"
                           "1000000000000,b,B,X,BUY,100,1,-1\n")
        self.assertEqual(s["trade_count"], 1)
        self.assertEqual(s["expired_orders"], 0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    args, remaining = parser.parse_known_args()
    BINARY = args.binary.resolve()
    unittest.main(argv=[__file__, *remaining], verbosity=2)
