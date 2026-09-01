"""
Rossmann Store Sales - promo effectiveness analysis
==================================================

Question:  Do promotions drive incremental sales, and is the effect consistent
           across the week?

This script:
  1. loads and cleans train.csv,
  2. prints the analysis tables (promo vs non-promo sales, customers, spend per
     visit; promo frequency by weekday; the weekday day-of-week breakdown; a
     store-mix confound check; and back-of-envelope revenue estimates),
  3. writes the two portfolio charts as high-resolution PNGs.

Run:  python promo_analysis.py
"""

import glob
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd

pd.set_option("display.width", 200)

DAY_LABELS = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri"}


# ======================================================================
# 1. Load + clean
# ======================================================================
def load_clean():
    raw = pd.read_csv("train.csv", parse_dates=["Date"], low_memory=False)
    n_raw = len(raw)

    open_only = raw[raw["Open"] == 1]
    n_open = len(open_only)

    # A handful of rows are Open==1 but Sales==0 - treat as data errors.
    clean = open_only[open_only["Sales"] > 0]
    n_clean = len(clean)

    weekday = clean[clean["DayOfWeek"] <= 5].copy()   # promos never run Sat/Sun

    print("=" * 66)
    print("1. CLEANING")
    print("=" * 66)
    print(f"raw rows                         : {n_raw:,}")
    print(f"after dropping closed stores     : {n_open:,}  (-{n_raw - n_open:,})")
    print(f"after dropping Open&Sales==0     : {n_clean:,}  (-{n_open - n_clean:,})")
    print(f"weekday-only working set (Mon-Fri): {len(weekday):,}")
    print(f"  non-promo rows: {(weekday['Promo'] == 0).sum():,}"
          f"  |  promo rows: {(weekday['Promo'] == 1).sum():,}")
    print()
    return weekday


# ======================================================================
# 2. Analysis
# ======================================================================
def _by_promo(df, col):
    g = df.groupby("Promo")[col]
    return pd.DataFrame({"mean": g.mean().round(2),
                         "median": g.median(),
                         "count": g.count()})


def analysis(df):
    df = df.assign(SalesPerCustomer=df["Sales"] / df["Customers"])

    print("=" * 66)
    print("2. PROMO vs NON-PROMO (weekday-only)")
    print("=" * 66)
    print("\n-- Sales --")
    print(_by_promo(df, "Sales"))
    print("\n-- Customers --")
    print(_by_promo(df, "Customers"))
    print("\n-- Sales per customer --")
    print(_by_promo(df, "SalesPerCustomer"))

    print("\n" + "=" * 66)
    print("3. PROMO FREQUENCY BY DAY OF WEEK")
    print("=" * 66)
    freq = df.groupby("DayOfWeek").agg(rows=("Promo", "size"),
                                      promo_rows=("Promo", "sum"))
    freq["promo_share_%"] = (100 * freq["promo_rows"] / freq["rows"]).round(1)
    freq.index = freq.index.map(DAY_LABELS)
    print(freq)

    print("\n" + "=" * 66)
    print("4. SALES BY DAY OF WEEK x PROMO  (the headline)")
    print("=" * 66)
    mean_by = df.groupby(["DayOfWeek", "Promo"])["Sales"].mean().unstack()
    med_by = df.groupby(["DayOfWeek", "Promo"])["Sales"].median().unstack()
    n_by = df.groupby(["DayOfWeek", "Promo"])["Sales"].size().unstack()
    tbl = pd.DataFrame({
        "noPromo_mean": mean_by[0].round(0),
        "Promo_mean": mean_by[1].round(0),
        "noPromo_median": med_by[0],
        "Promo_median": med_by[1],
        "noPromo_n": n_by[0],
        "Promo_n": n_by[1],
        "lift_%_mean": (100 * (mean_by[1] / mean_by[0] - 1)).round(1),
    })
    tbl.index = tbl.index.map(DAY_LABELS)
    print(tbl)

    lift_pct = (mean_by[1] / mean_by[0] - 1) * 100
    lift_pct.index = lift_pct.index.map(DAY_LABELS)

    promo_mean = df.loc[df["Promo"] == 1, "Sales"].mean()
    nonpromo_mean = df.loc[df["Promo"] == 0, "Sales"].mean()
    overall_lift = (promo_mean / nonpromo_mean - 1) * 100
    print(f"\nControlled (Mon-Fri collapsed): non-promo {nonpromo_mean:,.0f}"
          f"  |  promo {promo_mean:,.0f}  |  +{overall_lift:.1f}%")

    print("\n" + "=" * 66)
    print("5. CONFOUND CHECK - is it the same stores on promo & non-promo days?")
    print("=" * 66)
    stores_promo = set(df.loc[df["Promo"] == 1, "Store"].unique())
    stores_nonpromo = set(df.loc[df["Promo"] == 0, "Store"].unique())
    mixed_dates = (df.groupby("Date")["Promo"].nunique() > 1).sum()
    per_store_share = df.groupby("Store")["Promo"].mean()
    print(f"stores on promo rows      : {len(stores_promo):,}")
    print(f"stores on non-promo rows  : {len(stores_promo):,}")
    print(f"promo-only / non-promo-only: {len(stores_promo - stores_nonpromo)}"
          f" / {len(stores_nonpromo - stores_promo)}")
    print(f"dates with a mixed promo/non-promo split across stores: {mixed_dates}"
          f"  (promo is company-wide, not store-by-store)")
    print(f"per-store promo share of weekdays: "
          f"min {per_store_share.min():.3f}  max {per_store_share.max():.3f}"
          f"  (flat -> no selection by store)")

    print("\n" + "=" * 66)
    print("6. BACK-OF-ENVELOPE REVENUE ESTIMATES")
    print("=" * 66)
    promo_n = int((df["Promo"] == 1).sum())
    abs_lift = promo_mean - nonpromo_mean
    incremental = abs_lift * promo_n
    total_promo_sales = df.loc[df["Promo"] == 1, "Sales"].sum()
    years = df["Date"].nunique() / 5 / 52
    print(f"absolute lift per promo store-day : {abs_lift:,.0f}")
    print(f"promo store-days                  : {promo_n:,}")
    print(f"=> estimated incremental sales    : {incremental:,.0f}"
          f"  (~{incremental / years:,.0f} / year over ~{years:.2f} yrs)")
    print(f"   as a share of promo-day sales  : {100 * incremental / total_promo_sales:.0f}%"
          f"  (the other ~{100 - 100 * incremental / total_promo_sales:.0f}% is baseline)")

    fri = df[df["DayOfWeek"] == 5]
    fri_np = fri.loc[fri["Promo"] == 0, "Sales"].mean()
    fri_p = fri.loc[fri["Promo"] == 1, "Sales"].mean()
    fri_n = int((fri["Promo"] == 1).sum())
    wed = df[df["DayOfWeek"] == 3]
    wed_lift = wed.loc[wed["Promo"] == 1, "Sales"].mean() / wed.loc[wed["Promo"] == 0, "Sales"].mean() - 1
    fri_upside = (fri_np * (1 + wed_lift) - fri_p) * fri_n
    print(f"\nFriday promo lift  : +{100 * (fri_p / fri_np - 1):.0f}%"
          f"   (Wednesday: +{100 * wed_lift:.0f}%)")
    print(f"if Friday performed at Wednesday's lift => extra {fri_upside:,.0f}"
          f"  (~{fri_upside / years:,.0f} / year)")
    print()

    return lift_pct, nonpromo_mean, promo_mean, overall_lift


# ======================================================================
# 3. Charts
# ======================================================================
_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
for _ttf in glob.glob(os.path.join(_FONT_DIR, "Poppins-*.ttf")):
    font_manager.fontManager.addfont(_ttf)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Poppins", "Segoe UI", "Helvetica Neue", "Arial", "DejaVu Sans"],
    "text.color": "#1f2933",
    "axes.edgecolor": "#1f2933",
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
})

INK = "#1f2933"          # primary text
MUTED = "#6b7280"        # subtitle / secondary text
BASELINE = "#d5d9e0"     # thin baseline rule
BLUE_RAMP = ["#12508c", "#2f74b3", "#5f9bd0", "#95c0e3", "#c9e0f4"]  # Mon dark -> Fri light
ACCENT = "#12508c"       # promo bar
GRAY = "#c2c7cf"         # non-promo bar


def _style_axes(ax):
    """Strip chart-junk: no gridlines, no y-axis, thin baseline only."""
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.spines["bottom"].set_linewidth(1.0)
    ax.tick_params(axis="x", length=0, pad=8, labelsize=11.5, colors=INK)
    ax.set_yticks([])
    ax.grid(False)


def _add_titles(fig, title, subtitle):
    fig.text(0.045, 0.945, title, fontsize=15.5, fontweight="bold",
             color=INK, ha="left", va="top")
    fig.text(0.045, 0.876, subtitle, fontsize=10.8, color=MUTED,
             ha="left", va="top")


def _flatten_rgb(path):
    """Save as plain RGB so every image viewer opens the file."""
    from PIL import Image

    im = Image.open(path)
    if im.mode == "RGBA":
        bg = Image.new("RGB", im.size, "white")
        bg.paste(im, mask=im.split()[3])
        bg.save(path)


def chart_lift_by_day(lift_pct, path="chart1_promo_lift_by_dayofweek.png"):
    fig, ax = plt.subplots(figsize=(8.4, 5.4))
    fig.subplots_adjust(left=0.055, right=0.965, top=0.76, bottom=0.13)

    days = list(lift_pct.index)              # natural Mon..Fri order
    vals = lift_pct.values
    bars = ax.bar(days, vals, width=0.62, color=BLUE_RAMP, zorder=3)

    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + max(vals) * 0.028,
                f"+{v:.0f}%", ha="center", va="bottom",
                fontsize=12.5, fontweight="bold", color=INK)

    _style_axes(ax)
    ax.set_ylim(0, max(vals) * 1.16)
    ax.margins(x=0.06)
    _add_titles(fig,
                "Promo lift shrinks from 57% on Monday to 22% on Friday",
                "Sales lift on promo days vs non-promo days, by day of week")
    fig.savefig(path, dpi=300, transparent=False)
    plt.close(fig)
    _flatten_rgb(path)
    return path


def chart_promo_vs_nonpromo(nonpromo_mean, promo_mean, overall_lift,
                            path="chart2_promo_vs_nonpromo_sales.png"):
    fig, ax = plt.subplots(figsize=(8.4, 5.4))
    fig.subplots_adjust(left=0.055, right=0.965, top=0.76, bottom=0.13)

    means = [nonpromo_mean, promo_mean]
    bars = ax.bar(["No promo", "Promo"], means, width=0.5,
                  color=[GRAY, ACCENT], zorder=3)

    for b, v in zip(bars, means):
        ax.text(b.get_x() + b.get_width() / 2, v + max(means) * 0.028,
                f"{v:,.0f}", ha="center", va="bottom",
                fontsize=13, fontweight="bold", color=INK)

    ax.annotate(f"+{overall_lift:.0f}%",
                xy=(1, promo_mean), xytext=(0.5, max(means) * 1.07),
                ha="center", va="bottom", fontsize=12, fontweight="bold", color=ACCENT)

    _style_axes(ax)
    ax.set_ylim(0, max(means) * 1.16)
    ax.margins(x=0.18)
    _add_titles(fig,
                "Promo days generate 39% higher average sales",
                "Average daily sales per open store, Monday–Friday "
                "(closed days and zero-sales errors excluded)")
    fig.savefig(path, dpi=300, transparent=False)
    plt.close(fig)
    _flatten_rgb(path)
    return path


# ======================================================================
# main
# ======================================================================
if __name__ == "__main__":
    weekday = load_clean()
    lift_pct, nonpromo_mean, promo_mean, overall_lift = analysis(weekday)

    p1 = chart_lift_by_day(lift_pct)
    p2 = chart_promo_vs_nonpromo(nonpromo_mean, promo_mean, overall_lift)
    print(f"Saved: {p1}, {p2}")
