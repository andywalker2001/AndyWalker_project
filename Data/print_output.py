import ast
import os


def parse_file(filepath):
    with open(filepath, "r") as f:
        raw = f.read().strip()
    return ast.literal_eval(raw)


def print_aircraft_list(aircraft_list):
    print("=" * 60)
    print(f"  Aircraft  ({len(aircraft_list)} total)")
    print("=" * 60)
    for i, ac in enumerate(aircraft_list, 1):
        flight = ac.get("flight", "N/A").strip()
        print(f"\n  [{i}] Flight: {flight}")
        print(f"      {'Field':<20} {'Value'}")
        print(f"      {'-'*20} {'-'*20}")
        for key, value in ac.items():
            if key == "flight":
                continue
            print(f"      {key:<20} {value}")
    print()


output_path = os.path.join(os.path.dirname(__file__), "output.txt")
output = parse_file(output_path)

print("\n" + "=" * 60)
print("  output.txt — Aircraft")
print("=" * 60)
print_aircraft_list(output)
