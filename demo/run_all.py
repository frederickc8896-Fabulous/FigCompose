"""Run all demos at once for batch verification."""



import sys, os, subprocess



ROOT = os.path.dirname(os.path.abspath(__file__))



DEMOS = [

    "demo_bar_all.py",

    "demo_line_all.py",

    "demo_scatter_all.py",

    "demo_bar_meanline.py",

    "demo_box_meanline.py",

    "demo_stacked_bar.py",

    "demo_clustered_bar.py",

    "demo_clustered_box.py",

    "demo_clustered_line.py",

    "demo_clustered_scatter.py",

]



failed = []

for demo in DEMOS:

    path = os.path.join(ROOT, demo)

    print(f"=== {demo} ===", flush=True)

    rc = subprocess.run([sys.executable, path], cwd=ROOT).returncode

    if rc != 0:

        failed.append(demo)



print()

if failed:

    print(f"FAILED ({len(failed)}): {', '.join(failed)}")

else:

    print(f"ALL {len(DEMOS)} DEMOS PASSED")

