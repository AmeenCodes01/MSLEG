"""Streamlit front end. Run: streamlit run app.py"""
import altair as alt
import streamlit as st

from pipeline import run

st.set_page_config(page_title="Ethical Charity AI Analyst", layout="wide")
st.title("Ethical Charity AI Analyst")
st.caption("Turns a charity's values into a $100,000 portfolio, with every decision explained. "
           "Educational hackathon project. Not financial advice.")

DEFAULT = ("We are a cancer research charity funding early-detection research. We will not invest "
           "in weapons. We need moderate risk because we fund grants every year, "
           "and no single company should be more than 8% of the portfolio.")

policy_text = st.text_area("The charity's investment policy (plain English)", DEFAULT, height=120)

if st.button("Build portfolio", type="primary"):
    bar = st.progress(0.0, "Starting…")
    st.session_state.result = run(policy_text, progress=lambda f, m: bar.progress(min(f, 1.0), m))
    bar.empty()

res = st.session_state.get("result")
if res:
    port, scr = res["portfolio"], res["screen"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Companies scanned", res["companies_scanned"])
    c2.metric("Excluded", int((scr.status == "excluded").sum()))
    c3.metric("3-month T-bill yield", f"{res['rf']:.2%}")
    c4.metric("Historical return (est.)", f"{res['expected_return']:.1%}")

    pol = res["policy"]
    if pol.get("inferred_exclusions"):
        st.subheader("Exclusions the AI inferred from the charity's mission")
        for x in pol["inferred_exclusions"]:
            st.markdown(f"🧭 **{x.get('theme')}**: {x.get('reason')}")
    with st.expander("How the AI read the policy"):
        st.json(pol)

    left, right = st.columns([1, 1])
    with left:
        st.subheader("Where the $100,000 goes")
        by_class = port.groupby("asset_class", as_index=False)["dollars"].sum()
        st.altair_chart(
            alt.Chart(by_class).mark_arc(innerRadius=60).encode(
                theta="dollars:Q", color="asset_class:N",
                tooltip=["asset_class", alt.Tooltip("dollars:Q", format="$,.0f")]),
            use_container_width=True)
        if res["rate_note"]:
            st.info(res["rate_note"])
    with right:
        st.subheader("Holdings")
        st.dataframe(
            port[["ticker", "name", "industry", "asset_class", "dollars", "annual_return", "volatility",
                  "flagged"]].style.format({"dollars": "${:,.0f}", "annual_return": "{:.1%}",
                                            "volatility": "{:.1%}"}),
            use_container_width=True, hide_index=True)

    st.subheader("What the AI excluded or flagged, and why")
    for _, r in scr[scr.status.isin(["excluded", "flagged"])].iterrows():
        icon = "🚫" if r.status == "excluded" else "⚠️"
        line = f"{icon} **{r['name']} ({r.ticker})** · _{r.industry}_ · {r.stage}: {r.reason}"
        if r.evidence:
            line += f"  \n  _Evidence:_ {r.evidence}" + (f" ([source]({r.url}))" if r.url else "")
        st.markdown(line)

    st.subheader("Analyst memo for the trustees")
    st.markdown(res["memo"])
