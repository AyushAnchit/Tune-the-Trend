import streamlit as st # type: ignore
import httpx
import traceback
import datetime
from tune_the_trend.db.database import SessionLocal, init_db
from tune_the_trend.db.repository import (
    get_enabled_sources,
    sync_sources,
    get_all_active_trends_with_music
)
from tune_the_trend.db.models import DBScrapeRun, DBRecommendation
from tune_the_trend.services.recommendation import RecommendationEngine
from tune_the_trend.services.coordinator import run_pipeline
from tune_the_trend.models import CreatorProfile

st.set_page_config(page_title="Tune the Trend", layout="centered")

# Ensure DB is initialized and seeded if empty on startup
init_db()
db_startup = SessionLocal()
try:
    sync_sources(db_startup)
    
    import sys
    is_testing = "pytest" in sys.modules
    
    from tune_the_trend.db.models import DBTrendSignal
    if db_startup.query(DBTrendSignal).count() == 0 and not is_testing:
        run_pipeline(db_startup)
except Exception:
    pass
finally:
    db_startup.close()

st.title("Tune the Trend")
st.subheader("Find emerging trends and sounds for your next video.")

# API URL helper
API_URL = "http://localhost:8080"

def call_api(method, path, json_data=None, params=None):
    try:
        with httpx.Client(timeout=30.0) as client:
            if method == "POST":
                res = client.post(f"{API_URL}{path}", json=json_data, params=params)
            else:
                res = client.get(f"{API_URL}{path}", params=params)
            if res.status_code == 200:
                return res.json(), None
            elif res.status_code == 404:
                return None, "Not enough evidence yet"
            else:
                return None, f"Error {res.status_code}: {res.text}"
    except Exception:
        return None, "API connection failed"

allow_broader = True

# Fetch dynamic niches from database
default_niches = ["dance", "fashion", "fitness", "cooking", "travel", "beauty", "tech", "gaming", "comedy", "education"]
db_niches = set()
db_session = SessionLocal()
try:
    trends_in_db = get_all_active_trends_with_music(db_session)
    for t in trends_in_db:
        if t.niches:
            for n in t.niches:
                if n:
                    db_niches.add(n.lower().strip())
except Exception:
    pass
finally:
    db_session.close()

combined_niches = sorted(list(set(default_niches).union(db_niches)))

# Form Inputs
with st.form("creator_input_form"):
    st.write("### Creator Requirements")
    
    content_type_choice = st.radio(
        "What are you creating?",
        ["Short video", "Long-form video"]
    )
    
    niche = st.selectbox(
        "What's your niche?",
        options=combined_niches
    )
    
    desired_music = st.text_input(
        "What kind of music do you want?",
        placeholder="e.g. chill lofi, high-energy pop..."
    )
    
    description = st.text_area(
        "Describe your video (Optional)",
        placeholder="Tell us details about your content concept..."
    )
    
    submit_button = st.form_submit_button("Find Trends")

if submit_button:
    if not niche or not desired_music:
        st.error("Please fill in Niche and Music style fields.")
    else:
        profile = CreatorProfile(
            content_type="reels" if content_type_choice == "Short video" else "long_form",
            niche=niche,
            desired_music=desired_music,
            content_description=description
        )
        
        recs = None
        error_msg = None
        
        # Try API first
        with st.spinner("Finding trends..."):
            recs_json, api_err = call_api(
                "POST", 
                "/recommend", 
                json_data=profile.model_dump(), 
                params={"allow_broader": allow_broader}
            )
            
            if api_err is None and recs_json:
                recs = recs_json
            else:
                # Local fallback execution
                db = SessionLocal()
                try:
                    engine = RecommendationEngine(db)
                    recs_objs = engine.generate_recommendations(profile, allow_broader=allow_broader)
                    if recs_objs:
                        recs = [r.model_dump() for r in recs_objs]
                    else:
                        error_msg = "Not enough evidence yet"
                except Exception as local_err:
                    error_msg = f"Recommendation failed: {str(local_err)}"
                finally:
                    db.close()
                    
        if error_msg == "Not enough evidence yet" or (not recs and error_msg is None):
            st.warning("⚠️ **Not enough evidence yet**")
            st.info("No matching trend evidence was found. Try enabling **'Broader Matches'** in the sidebar fallback mode to widen filters.")
        elif error_msg:
            st.error(error_msg)
        else:
            st.write(f"### Top 5 Recommendations")
            for idx, rec in enumerate(recs or []):
                cand = rec["candidate"]
                trend_sig = cand["trend_signal"]
                music_ev = cand["music_evidence"]
                
                # Render Clean Result Page Block
                song_url = music_ev.get("spotify_url") if music_ev else None
                preview_url = music_ev.get("preview_url") if music_ev else None
                
                if song_url:
                    st.markdown(f"#### {idx+1}. 🎧 [Listen to {rec['track']} by {rec['artist']}]({song_url})")
                else:
                    st.markdown(f"#### {idx+1}. 🎵 {rec['track']} by {rec['artist']}")
                
                # 30-Second Playable Audio Player
                if preview_url:
                    st.caption("▶️ **30-Second Live Track Preview**")
                    st.audio(preview_url, format="audio/mp3")
                elif song_url:
                    st.caption("🔗 [Open Track Stream on Deezer Platform]({})".format(song_url))
                
                p_music_pct = int(rec.get("p_music_similarity", 0.85) * 100)
                p_viral_pct = int(rec.get("p_virality_potential", 0.80) * 100)
                p_concept_pct = int(rec.get("p_concept_relevance", 0.90) * 100)
                v_tier = rec.get("virality_tier", "High Momentum")

                col1, col2, col3 = st.columns(3)
                col1.metric("Probabilistic Match", f"{int(rec['creator_match_score']*100)}%")
                col2.metric("Audio Similarity P(Music)", f"{p_music_pct}%")
                col3.metric("Virality P(Viral)", f"{p_viral_pct}% ({v_tier})")
                
                st.markdown(f"**Trend:** {rec['trend_name']} ({trend_sig['platform'].capitalize()})")
                
                # PROBABILISTIC MATCH JUSTIFICATION
                st.markdown(f"🎯 **PROBABILISTIC SIMILARITY ANALYSIS**\n- **Concept Relevance P(Concept)**: `{p_concept_pct}%` | **Music Fit P(Audio)**: `{p_music_pct}%` | **Virality Potential P(Viral)**: `{p_viral_pct}%` ({v_tier})")
                st.markdown(f"💡 **WHY THIS MATCHES YOUR CONCEPT**\n*{rec['why_it_matches']}*")
                # WHY NOW
                st.markdown(f"⚡ **WHY NOW**\n*{rec['why_now']}*")
                
                # EVIDENCE & MUSIC BASIS
                basis_type = "Explicit song match" if music_ev and music_ev.get("spotify_id") else "Inferred music characteristics"
                st.markdown(f"📝 **EVIDENCE ARTICLE**\n- Source: `{trend_sig['source_id']}`\n- Source Article: [{rec['source_url']}]({rec['source_url']})\n- Scraped Date: {trend_sig['scraped_at'][:10]}")
                
                track_link_markdown = f"[{rec['track']} by {rec['artist']}]({song_url})" if song_url else f"{rec['track']} by {rec['artist']}"
                st.markdown(f"🎵 **MUSIC AUDIO BASIS**\n- Track: **{track_link_markdown}**\n- Matching Type: {basis_type} (Confidence: {int(rec['evidence_confidence']*100)}%)")
                
                # SOUND DETAILS (Collapsible Expander)
                energy_val = int((music_ev.get("energy") or 0.65) * 100) if music_ev else 65
                tempo_val = int(music_ev.get("tempo") or 115) if music_ev else 115
                valence_val = int((music_ev.get("valence") or 0.55) * 100) if music_ev else 55
                genres_list = music_ev.get("genres") or [profile.desired_music or profile.niche]
                
                with st.expander("🎵 Sound Details", expanded=False):
                    st.markdown(
                        f"- 🎻 **Instrumentation / Style**: `{', '.join(genres_list)}` \n"
                        f"- 🥁 **Tempo & BPM**: `{tempo_val} BPM` ({'Slow Focus Pace' if tempo_val <= 85 else ('Moderate Pace' if tempo_val <= 120 else 'Driving Fast Pace')})\n"
                        f"- ⚡ **Energy Level**: `{energy_val}%` ({'Low Energy / Calm Focus' if energy_val <= 45 else ('Moderate Energy' if energy_val <= 75 else 'High Energy Drop')})\n"
                        f"- 🎭 **Musical Mood**: `{valence_val}% Positive` ({'Serene & Calm' if valence_val <= 50 else 'Uplifting & Bright'})\n"
                    )
                
                # How we found this
                with st.expander("🔬 How we found this"):
                    st.markdown("""
                    **Candidate generation**
                    ↓
                    **Ranking**
                    ↓
                    **Reranking**
                    """)
                    
                st.markdown("---")
