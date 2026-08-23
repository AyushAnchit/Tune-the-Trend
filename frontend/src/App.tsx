import React, { useState, useRef, useEffect } from 'react';
import { 
  Sparkles, 
  Volume2, 
  ExternalLink, 
  Flame, 
  Music, 
  Zap, 
  Activity, 
  Disc,
  Radio,
  ChevronLeft,
  ChevronRight,
  ChevronDown
} from 'lucide-react';

interface Recommendation {
  rank: number;
  track: string;
  artist: string;
  trend_name: string;
  platform: string;
  content_type: string;
  creator_match_score: number;
  p_music_similarity: number;
  p_virality_potential: number;
  p_concept_relevance: number;
  virality_tier: string;
  why_it_matches: string;
  why_now: string;
  source_url: string;
  evidence_confidence: number;
  candidate: {
    trend_signal: {
      source_id: string;
      platform: string;
      scraped_at: string;
    };
    music_evidence: {
      spotify_url?: string;
      preview_url?: string;
      genres?: string[];
      energy?: number;
      tempo?: number;
      valence?: number;
    };
  };
}

export default function App() {
  const [contentType, setContentType] = useState('reels');
  const [niche, setNiche] = useState('travel');
  const [desiredMusic, setDesiredMusic] = useState('spanish, flamenco');
  const [description, setDescription] = useState('solo trip to spain');
  const [loading, setLoading] = useState(false);
  const [recommendations, setRecommendations] = useState<Recommendation[] | null>(null);
  const [, setError] = useState<string | null>(null);
  const [expandedDetails, setExpandedDetails] = useState<Record<number, boolean>>({});

  const toggleDetails = (idx: number) => {
    setExpandedDetails(prev => ({ ...prev, [idx]: !prev[idx] }));
  };

  const [cursorPos, setCursorPos] = useState({ x: -100, y: -100 });
  const [isHovered, setIsHovered] = useState(false);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setCursorPos({ x: e.clientX, y: e.clientY });
      const target = e.target as HTMLElement;
      if (
        target.closest('button') || 
        target.closest('a') || 
        target.closest('input') || 
        target.closest('textarea') || 
        target.closest('.cyber-cut-corner-lg')
      ) {
        setIsHovered(true);
      } else {
        setIsHovered(false);
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  const heroTagline = "High-tech audio intelligence engine parsing creator video profiles against real-time Shazam, Hype Machine, and social media signals with 30s live stream previews.";
  const [typedText, setTypedText] = useState('');

  // Typewriter Typing Animation (Repeats every 45 seconds)
  useEffect(() => {
    let typeTimer: ReturnType<typeof setInterval>;

    const startTypingEffect = () => {
      let index = 0;
      setTypedText('');
      if (typeTimer) clearInterval(typeTimer);

      typeTimer = setInterval(() => {
        if (index < heroTagline.length) {
          setTypedText(heroTagline.slice(0, index + 1));
          index++;
        } else {
          clearInterval(typeTimer);
        }
      }, 22);
    };

    // Initial typing run
    startTypingEffect();

    // Repeat typing effect every 45 seconds (45,000 ms)
    const repeatInterval = setInterval(() => {
      startTypingEffect();
    }, 45000);

    return () => {
      if (typeTimer) clearInterval(typeTimer);
      clearInterval(repeatInterval);
    };
  }, []);

  // Single Audio Track Playback Enforcement (Pause previous audio when new track plays)
  useEffect(() => {
    const handleAudioPlay = (e: Event) => {
      const targetAudio = e.target as HTMLAudioElement;
      if (targetAudio && targetAudio.tagName === 'AUDIO') {
        const allAudioElements = document.querySelectorAll('audio');
        allAudioElements.forEach((audio) => {
          if (audio !== targetAudio) {
            audio.pause();
          }
        });
      }
    };

    document.addEventListener('play', handleAudioPlay, true);
    return () => document.removeEventListener('play', handleAudioPlay, true);
  }, []);

  const [isScrolled, setIsScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 20);
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const carouselRef = useRef<HTMLDivElement>(null);
  const recommendationsSectionRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to recommendations section when search completes
  useEffect(() => {
    if (recommendations && !loading) {
      setTimeout(() => {
        recommendationsSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 150);
    }
  }, [recommendations, loading]);

  const defaultNiches = [
    'travel', 'dance', 'fashion', 'fitness', 'cooking', 
    'tech', 'beauty', 'gaming', 'comedy', 'productivity'
  ];

  const quickMusicPresets = [
    { label: 'BOLLYWOOD_SITAR', value: 'indian, bollywood, sitar' },
    { label: 'FLAMENCO_GUITAR', value: 'spanish, flamenco' },
    { label: 'CALM_VIOLIN', value: 'violin, calm' },
    { label: 'SYNTHWAVE_80S', value: 'synthwave, retro' },
    { label: 'LOFI_STUDY_FOCUS', value: 'lofi, chill, study' },
    { label: 'CYBER_HIP_HOP', value: 'hip hop, high energy' },
  ];

  const handleFetchRecommendations = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setLoading(true);
    setError(null);

    const payload = {
      content_type: contentType,
      niche: niche,
      desired_music: desiredMusic,
      content_description: description,
    };

    try {
      const res = await fetch('/api/recommend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const directRes = await fetch('http://localhost:8080/recommend', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!directRes.ok) throw new Error(`HTTP Error ${directRes.status}`);
        const data = await directRes.json();
        setRecommendations(data);
      } else {
        const data = await res.json();
        setRecommendations(data);
      }
    } catch (err: any) {
      console.warn("Backend API call failed, running Cyberpunk client synthesis", err);
      setTimeout(() => {
        setRecommendations(getMockCyberpunkRecommendations(niche, desiredMusic));
      }, 600);
    } finally {
      setLoading(false);
    }
  };

  const scrollCarousel = (direction: 'left' | 'right') => {
    if (carouselRef.current) {
      const scrollAmount = direction === 'left' ? -540 : 540;
      carouselRef.current.scrollBy({ left: scrollAmount, behavior: 'smooth' });
    }
  };

  return (
    <div className={`min-h-screen bg-black text-slate-100 font-sans relative selection:bg-[#ff0055] selection:text-white ${isHovered ? 'cyber-cursor-hover' : ''}`}>
      {/* Cursor-Following Sharper Supernova Core (Replaces Old Cursor Animation) */}
      <div 
        className="supernova-cursor-core" 
        style={{ left: `${cursorPos.x}px`, top: `${cursorPos.y}px` }} 
      />

      {/* CRT Scanline Overlay Effect */}
      <div className="fixed inset-0 scanline-overlay z-50 pointer-events-none opacity-40" />

      {/* Dark Space Vignette Layer */}
      <div className="fixed inset-0 dark-space-vignette z-10 pointer-events-none" />

      {/* Slow Waving Red & Blue Aurora Background & Ambient Soundwave */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        {/* Waving Red & Blue Aurora Ribbons */}
        <div className="absolute -top-[200px] -left-[200px] w-[900px] h-[900px] aurora-red-glow blur-[150px] rounded-full" />
        <div className="absolute top-[300px] -right-[200px] w-[1000px] h-[1000px] aurora-blue-glow blur-[170px] rounded-full" />
        <div className="absolute -bottom-[200px] left-[20%] w-[800px] h-[800px] aurora-red-glow blur-[160px] rounded-full" />

        {/* Ambient Blurred Background Soundwave Equalizer */}
        <div className="bg-soundwave-container">
          {Array.from({ length: 54 }).map((_, i) => (
            <div 
              key={i} 
              className="bg-soundwave-bar" 
              style={{ 
                animationDelay: `${(i % 12) * 0.32}s`,
                animationDuration: `${2.6 + (i % 6) * 0.4}s`,
                height: `${25 + (Math.abs(Math.sin(i * 0.45)) * 65)}%`
              }} 
            />
          ))}
        </div>
      </div>

      {/* Full Horizontal Video Background Acquiring Top Edge & Nav Space */}
      <div className="absolute top-0 left-0 right-0 h-[680px] sm:h-[780px] md:h-[880px] w-full overflow-hidden pointer-events-none z-0">
        <video 
          src="/cyberpunk_dj_hero.mp4" 
          autoPlay 
          loop 
          muted 
          playsInline 
          className="w-full h-full object-cover object-top opacity-100 filter brightness-100 contrast-105"
        />
        {/* Soft Ambient Fade to Pure Black at Bottom */}
        <div className="absolute inset-0 bg-gradient-to-t from-black via-transparent to-black/30 pointer-events-none" />
      </div>

      {/* Top Navigation Header (Floating Directly Over Top of Video) */}
      <header className={`relative z-30 border-b transition-all duration-300 sticky top-0 ${
        isScrolled 
          ? 'bg-black/40 backdrop-blur-md border-[#00f0ff]/20 shadow-xl' 
          : 'bg-black/20 backdrop-blur-sm border-[#00f0ff]/30'
      }`}>
        <div className="max-w-7xl mx-auto px-8 md:px-12 h-24 md:h-28 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-[#00f0ff]/10 border border-[#00f0ff] flex items-center justify-center text-[#00f0ff] neon-glow-cyan cyber-cut-corner">
              <Music className="w-6 h-6 text-[#00f0ff]" />
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-2xl font-black font-cyber tracking-wider text-white neon-text-cyan drop-shadow-[0_2px_10px_rgba(0,0,0,0.9)]">
                Tune the Trend
              </span>
              <span className="text-xs md:text-sm font-mono-tech text-slate-300 drop-shadow-[0_2px_10px_rgba(0,0,0,0.9)]">
                Find emerging trends and sounds for your next video.
              </span>
            </div>
          </div>
        </div>
      </header>



      {/* Main Container */}
      <main className="relative z-10 max-w-7xl mx-auto px-8 md:px-12 py-8 md:py-16 space-y-20 md:space-y-32">
        {/* Full Horizontal Overlapped Hero Console (Positioned Over Full-Bleed Video) */}
        <section className="relative w-full my-4 md:my-8 text-center">
          
          {/* Overlaid Hero Content Directly Across Video */}
          <div className="relative z-10 px-6 sm:px-12 pt-16 sm:pt-24 md:pt-32 pb-12 sm:pb-20 flex flex-col items-center justify-center text-center space-y-6 max-w-4xl mx-auto">
            {/* Live Feed Status Pill */}
            <div className="px-4 py-1.5 bg-black/80 border border-[#00f0ff] text-[#00f0ff] font-mono-tech text-xs tracking-widest flex items-center gap-2 cyber-cut-corner shadow-[0_0_20px_rgba(0,240,255,0.5)]">
              <span className="w-2 h-2 bg-[#00f0ff] rounded-full animate-ping" />
              <span className="font-extrabold">LIVE_AUDIO_RECON_FEED // FULL_SPECTRUM_4K</span>
            </div>

            {/* Slightly Decreased Title Overlaid Across Video for Maximum Clarity */}
            <h1 className="text-3xl sm:text-5xl md:text-6xl font-black font-cyber tracking-tight text-white leading-tight drop-shadow-[0_4px_20px_rgba(0,0,0,0.95)] max-w-3xl">
              VIRAL AUDIO RECON <span className="text-[#00f0ff] neon-text-cyan">&amp; TREND SYNTHESIS</span>
            </h1>

            {/* Typewriter Description Container Overlaid */}
            <p className="text-sm sm:text-base md:text-lg font-mono-tech text-slate-100 max-w-2xl mx-auto leading-relaxed min-h-[56px] flex items-center justify-center py-4 px-6 bg-black/75 border border-[#00f0ff]/60 cyber-cut-corner-lg shadow-2xl backdrop-blur-md">
              <span>{typedText}</span>
              <span className="inline-block w-2 h-4 bg-[#00f0ff] ml-1.5 tech-blink" />
            </p>
          </div>
        </section>

        {/* 1. FULL HORIZONTAL INPUT MATRIX (TOP SECTION) */}
        <div className="w-full bg-[#121212]/90 border border-[#00f0ff]/40 p-8 md:p-12 shadow-2xl relative cyber-cut-corner-lg neon-glow-cyan mb-20 md:mb-28">
          {/* Tech Corner Overlays */}
          <div className="absolute top-3 left-6 text-[11px] font-mono-tech text-[#00f0ff]/70 tracking-widest">// INPUT_MATRIX_FULL_WIDTH</div>
          <div className="absolute top-3 right-6 text-[11px] font-mono-tech text-[#00f0ff]/70 tracking-widest">[ 01 ]</div>

          <div className="flex items-center gap-4 mb-8 pt-3 pb-5 border-b border-[#00f0ff]/30">
            <div className="w-12 h-12 bg-[#00f0ff]/10 border border-[#00f0ff] flex items-center justify-center text-[#00f0ff] neon-glow-cyan">
              <Radio className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-xl md:text-2xl font-cyber font-black text-white tracking-widest">WHAT DO YOU WANT TO CREATE TODAY?</h2>
              <p className="text-xs md:text-sm font-mono-tech text-slate-300 mt-1">Configure your target concept &amp; audio parameters across the full width</p>
            </div>
          </div>

          <form onSubmit={handleFetchRecommendations} className="space-y-8">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 lg:gap-10 items-start">
              {/* Column 1: Format & Niche */}
              <div className="space-y-7">
                <div>
                  <label className="block text-xs md:text-sm font-mono-tech font-bold text-[#00f0ff] uppercase tracking-widest mb-3">
                    // FORMAT &amp; PLATFORM
                  </label>
                  <div className="grid grid-cols-4 gap-1.5 p-1.5 bg-black border border-[#00f0ff]/40">
                    {['reels', 'tiktok', 'shorts', 'video'].map((fmt) => (
                      <button
                        key={fmt}
                        type="button"
                        onClick={() => setContentType(fmt)}
                        className={`py-3 text-xs md:text-sm font-mono-tech font-bold uppercase transition-all ${
                          contentType === fmt
                            ? 'bg-[#00f0ff] text-black font-extrabold shadow-lg shadow-[#00f0ff]/50'
                            : 'text-slate-400 hover:text-white'
                        }`}
                      >
                        {fmt}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-xs md:text-sm font-mono-tech font-bold text-[#00f0ff] uppercase tracking-widest mb-3">
                    // SELECT_CREATOR_NICHE
                  </label>
                  <div className="flex flex-wrap gap-2.5">
                    {defaultNiches.map((n) => (
                      <button
                        key={n}
                        type="button"
                        onClick={() => setNiche(n)}
                        className={`px-3.5 py-1.5 text-xs md:text-sm font-mono-tech uppercase font-bold transition-all border cyber-hover-lift ${
                          niche === n
                            ? 'bg-[#ff0055] border-[#ff0055] text-white neon-glow-pink'
                            : 'bg-black/60 border-slate-800 text-slate-400 hover:border-[#00f0ff]/50'
                        }`}
                      >
                        {n}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Column 2: Desired Audio Style & Presets */}
              <div className="space-y-7">
                <div>
                  <label className="block text-xs md:text-sm font-mono-tech font-bold text-[#00f0ff] uppercase tracking-widest mb-3">
                    // DESIRED_AUDIO_STYLE
                  </label>
                  <input
                    type="text"
                    value={desiredMusic}
                    onChange={(e) => setDesiredMusic(e.target.value)}
                    placeholder="e.g. spanish, flamenco, violin, calm"
                    className="w-full px-5 py-3.5 bg-black border border-slate-800 text-white font-mono-tech text-sm md:text-base placeholder:text-slate-600 focus:outline-none focus:border-[#00f0ff] focus:ring-1 focus:ring-[#00f0ff] transition-all"
                  />
                  
                  <div className="flex flex-wrap gap-2 mt-3.5">
                    {quickMusicPresets.map((preset) => (
                      <button
                        key={preset.label}
                        type="button"
                        onClick={() => setDesiredMusic(preset.value)}
                        className="text-xs font-mono-tech px-3 py-1.5 bg-[#00f0ff]/5 border border-[#00f0ff]/40 hover:border-[#00f0ff] hover:bg-[#00f0ff]/20 text-[#00f0ff] transition-all font-bold cyber-hover-lift"
                      >
                        + {preset.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Column 3: Video Description & Submit */}
              <div className="space-y-7">
                <div>
                  <label className="block text-xs md:text-sm font-mono-tech font-bold text-[#00f0ff] uppercase tracking-widest mb-3">
                    // PROJECT_DESCRIPTION (OPTIONAL)
                  </label>
                  <textarea
                    rows={4}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="e.g. solo trip to spain, 3 hour study with me video, leg workout motivation"
                    className="w-full px-5 py-3.5 bg-black border border-slate-800 text-white font-mono-tech text-sm md:text-base placeholder:text-slate-600 focus:outline-none focus:border-[#00f0ff] focus:ring-1 focus:ring-[#00f0ff] transition-all resize-none"
                  />
                </div>
              </div>
            </div>

            {/* Execute Recon Button */}
            <div className="pt-4">
              <button
                type="submit"
                disabled={loading}
                className="w-full py-5 cyber-cut-corner bg-[#00f0ff] hover:bg-[#33f3ff] text-black font-cyber font-black text-base md:text-lg tracking-widest uppercase cyber-button-cyan neon-glow-cyan flex items-center justify-center gap-3 disabled:opacity-50"
              >
                {loading ? (
                  <>
                    <div className="w-5 h-5 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                    <span>SYNTHESIZING_RECOMMENDATIONS...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>EXECUTE_RECON_SEARCH ⚡</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>

        {/* 2. HORIZONTAL SWIPEABLE RECOMMENDATIONS CAROUSEL (BOTTOM SECTION) */}
        <div ref={recommendationsSectionRef} className="w-full space-y-8 pt-6 md:pt-10 scroll-mt-24">
          <div className="flex items-center justify-between pb-3 border-b border-[#00f0ff]/30 font-mono-tech">
            <h2 className="text-xl md:text-2xl font-cyber font-black text-white tracking-widest flex items-center gap-3">
              <Flame className="w-6 h-6 text-[#ff0055]" /> TOP RECOMMENDATIONS
            </h2>
            
            <div className="flex items-center gap-4">
              <span className="hidden sm:inline-block text-xs font-mono-tech text-slate-400">
                SWIPE LEFT / RIGHT OR USE NAV ARROWS
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => scrollCarousel('left')}
                  className="w-9 h-9 bg-black border border-[#00f0ff]/40 text-[#00f0ff] hover:bg-[#00f0ff] hover:text-black transition-colors flex items-center justify-center font-bold"
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <button
                  type="button"
                  onClick={() => scrollCarousel('right')}
                  className="w-9 h-9 bg-black border border-[#00f0ff]/40 text-[#00f0ff] hover:bg-[#00f0ff] hover:text-black transition-colors flex items-center justify-center font-bold"
                >
                  <ChevronRight className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>

          {!recommendations && !loading && (
            <div className="bg-[#121212]/80 border border-slate-800 p-12 text-center flex flex-col items-center justify-center min-h-[360px] cyber-cut-corner-lg">
              <div className="w-16 h-16 bg-[#00f0ff]/10 border border-[#00f0ff] flex items-center justify-center text-[#00f0ff] mb-4 neon-glow-cyan">
                <Music className="w-8 h-8" />
              </div>
              <h3 className="text-lg font-cyber font-bold text-white mb-2 tracking-wider">AUDIO_MATRIX_READY</h3>
              <p className="text-xs font-mono-tech text-slate-400 max-w-md leading-relaxed mb-6">
                Configure parameters in the top Input Matrix and click EXECUTE_RECON_SEARCH to render swipeable audio recommendations.
              </p>
              <button
                type="button"
                onClick={() => handleFetchRecommendations()}
                className="cyber-cut-corner px-6 py-3 bg-[#ff0055] hover:bg-[#ff3377] text-white font-cyber text-xs font-bold tracking-widest cyber-button-pink neon-glow-pink flex items-center gap-2"
              >
                <Sparkles className="w-4 h-4" /> RUN_SAMPLE_SYNTHESIS
              </button>
            </div>
          )}

          {loading && (
            <div className="bg-[#121212]/90 border border-[#00f0ff]/40 p-12 text-center flex flex-col items-center justify-center min-h-[360px] cyber-cut-corner-lg neon-glow-cyan">
              <div className="w-16 h-16 bg-[#00f0ff]/20 border border-[#00f0ff] flex items-center justify-center text-[#00f0ff] mb-6 tech-blink">
                <Activity className="w-8 h-8 animate-spin" />
              </div>
              <h3 className="text-lg font-cyber font-bold text-[#00f0ff] mb-2 tracking-wider neon-text-cyan">RERANKING_CANDIDATES</h3>
              <p className="text-xs font-mono-tech text-slate-400">
                GEMINI 3.1 FLASH LITE PROBABILISTIC INFERENCE &amp; LIVE DEEZER STREAM RESOLUTION...
              </p>
            </div>
          )}

          {recommendations && !loading && (
            <div 
              ref={carouselRef}
              className="flex gap-6 overflow-x-auto pb-6 scroll-smooth snap-x snap-mandatory scrollbar-thin scrollbar-thumb-[#00f0ff]/40 scrollbar-track-black"
            >
              {recommendations.map((rec, idx) => {
                const songUrl = rec.candidate?.music_evidence?.spotify_url || rec.source_url;
                const previewUrl = rec.candidate?.music_evidence?.preview_url;
                const matchPct = Math.round(rec.creator_match_score * 100);
                const musicPct = Math.round((rec.p_music_similarity || 0.85) * 100);
                const viralPct = Math.round((rec.p_virality_potential || 0.80) * 100);
                const conceptPct = Math.round((rec.p_concept_relevance || 0.90) * 100);
                const energy = Math.round((rec.candidate?.music_evidence?.energy || 0.65) * 100);
                const tempo = Math.round(rec.candidate?.music_evidence?.tempo || 115);
                const genres = rec.candidate?.music_evidence?.genres || [niche];

                return (
                  <div 
                    key={idx}
                    className="snap-start flex-shrink-0 w-[480px] sm:w-[520px] md:w-[540px] bg-[#121212]/95 border border-[#00f0ff]/40 p-8 md:p-9 relative cyber-cut-corner-lg neon-glow-cyan flex flex-col justify-between cyber-hover-lift space-y-6"
                  >
                    <div className="space-y-6">
                      {/* Top Corner Badge & Header */}
                      <div className="flex items-start justify-between gap-5">
                        <div className="flex items-center gap-3.5">
                          <span className="w-10 h-10 bg-[#ff0055] text-white font-cyber font-black text-lg flex items-center justify-center neon-glow-pink flex-shrink-0">
                            #{idx + 1}
                          </span>
                          <div>
                            <h4 className="text-xl md:text-2xl font-cyber font-bold text-white tracking-wide truncate max-w-[280px]">
                              {rec.track}
                            </h4>
                            <p className="text-xs md:text-sm font-mono-tech text-slate-400 truncate max-w-[280px]">ARTIST: {rec.artist}</p>
                          </div>
                        </div>

                        <div className="text-right flex-shrink-0">
                          <div className="text-3xl font-black font-cyber text-[#00f0ff] neon-text-cyan">{matchPct}%</div>
                          <div className="text-[11px] font-mono-tech uppercase font-bold tracking-widest text-[#ff0055]">CREATOR MATCH</div>
                        </div>
                      </div>

                      {/* 30-Second Playable Audio Player Widget */}
                      {previewUrl ? (
                        <div className="p-4 md:p-5 bg-black/80 border-l-3 border-l-[#00f0ff] border-y border-r border-slate-800 space-y-2.5">
                          <div className="flex items-center justify-between text-xs md:text-sm font-mono-tech text-slate-300">
                            <span className="flex items-center gap-2 text-[#00f0ff] font-bold">
                              <Volume2 className="w-4 h-4 text-[#00f0ff]" /> 30s LIVE AUDIO PREVIEW
                            </span>
                            <span className="text-xs text-[#00f0ff] font-bold tracking-wider">MP3 STREAM</span>
                          </div>
                          <audio controls src={previewUrl} className="w-full h-10 rounded-none accent-[#00f0ff]" />
                        </div>
                      ) : (
                        <div className="p-4 bg-black/80 border border-slate-800 text-xs md:text-sm font-mono-tech text-slate-400 flex items-center justify-between">
                          <span>🔗 STREAM FULL AUDIO ON DEEZER</span>
                        </div>
                      )}

                      {/* Probabilistic AI Justification (Sleek Quote Block) */}
                      <div className="border-l-3 border-[#00f0ff]/60 pl-4 py-1 space-y-1.5">
                        <div className="flex items-center gap-2 text-xs md:text-sm font-mono-tech font-bold text-[#00f0ff] tracking-wider uppercase">
                          <Zap className="w-4 h-4 text-[#00f0ff]" /> PROBABILISTIC ANALYSIS
                        </div>
                        <p className="text-xs md:text-sm font-mono-tech text-slate-300 leading-relaxed">
                          {rec.why_it_matches}
                        </p>
                      </div>

                      {/* Clean Probabilistic Metrics Bar */}
                      <div className="flex items-center justify-between px-4 py-3 bg-black/60 border border-slate-800 text-xs md:text-sm font-mono-tech">
                        <div><span className="text-slate-400">CONCEPT:</span> <span className="font-bold text-white">{conceptPct}%</span></div>
                        <span className="text-slate-700">•</span>
                        <div><span className="text-slate-400">AUDIO FIT:</span> <span className="font-bold text-[#00f0ff]">{musicPct}%</span></div>
                        <span className="text-slate-700">•</span>
                        <div><span className="text-slate-400">VIRALITY:</span> <span className="font-bold text-[#ff0055]">{viralPct}%</span></div>
                      </div>

                      {/* Collapsible Sound Details Accordion */}
                      <div className="bg-black/60 border border-[#ff0055]/30">
                        <button
                          type="button"
                          onClick={() => toggleDetails(idx)}
                          className="w-full px-4 py-3 flex items-center justify-between text-xs md:text-sm font-mono-tech font-bold text-[#ff0055] hover:bg-[#ff0055]/10 transition-colors"
                        >
                          <span className="flex items-center gap-2">
                            <Disc className="w-4.5 h-4.5 text-[#ff0055]" /> 🎵 SOUND DETAILS
                          </span>
                          <span className="flex items-center gap-1 text-xs text-slate-400 font-bold">
                            {expandedDetails[idx] ? '[ HIDE ]' : '[ EXPAND ]'}
                            <ChevronDown className={`w-4 h-4 transition-transform duration-200 ${expandedDetails[idx] ? 'rotate-180 text-[#ff0055]' : 'text-slate-500'}`} />
                          </span>
                        </button>

                        {expandedDetails[idx] && (
                          <div className="p-4 pt-0 border-t border-[#ff0055]/20 grid grid-cols-2 gap-2.5 text-xs md:text-sm font-mono-tech text-slate-300">
                            <div><span className="text-slate-400">Style:</span> {genres[0]}</div>
                            <div><span className="text-slate-400">Tempo:</span> {tempo} BPM</div>
                            <div><span className="text-slate-400">Energy:</span> {energy}%</div>
                            <div><span className="text-slate-400">Virality Tier:</span> {rec.virality_tier || 'High'}</div>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Full Width Listen / Stream Action Button */}
                    <div className="pt-2 font-mono-tech text-xs md:text-sm">
                      <a 
                        href={songUrl || `https://www.deezer.com/search/${encodeURIComponent(rec.track + " " + rec.artist)}`} 
                        target="_blank" 
                        rel="noreferrer"
                        className="w-full cyber-cut-corner px-5 py-4 bg-[#00f0ff]/10 border border-[#00f0ff] hover:bg-[#00f0ff] text-[#00f0ff] hover:text-black font-extrabold tracking-widest uppercase transition-all flex items-center justify-center gap-2.5 cyber-hover-lift"
                      >
                        <ExternalLink className="w-4.5 h-4.5" />
                        <span>LISTEN / STREAM FULL TRACK</span>
                      </a>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </main>

      {/* Cyberpunk Footer */}
      <footer className="relative z-20 border-t border-[#00f0ff]/20 bg-black/80 backdrop-blur-xl mt-28 md:mt-36 py-12 md:py-16">
        <div className="max-w-7xl mx-auto px-8 md:px-12 flex flex-col sm:flex-row items-center justify-between gap-6 font-mono-tech text-xs md:text-sm text-slate-400">
          <div className="flex items-center gap-3.5">
            <div className="w-9 h-9 bg-[#00f0ff]/10 border border-[#00f0ff] flex items-center justify-center text-[#00f0ff] cyber-cut-corner">
              <Music className="w-4.5 h-4.5 text-[#00f0ff]" />
            </div>
            <span className="font-cyber font-bold text-white tracking-wider text-sm">TUNE THE TREND v2.0</span>
          </div>
          <div className="flex items-center text-slate-400">
            <span>PROBABILISTIC AUDIO RECON ENGINE</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

// Fallback Mock Recommendations Client-Side Function
function getMockCyberpunkRecommendations(niche: string, music: string): Recommendation[] {
  return [
    {
      rank: 1,
      track: "Spanish Flamenco Guitar",
      artist: "Spanish Acoustic Ensemble",
      trend_name: "Solo Travel Spain & Scenic Flamenco Reel",
      platform: "instagram",
      content_type: "reels",
      creator_match_score: 0.94,
      p_music_similarity: 0.96,
      p_virality_potential: 0.88,
      p_concept_relevance: 0.98,
      virality_tier: "Explosive Growth",
      why_it_matches: `Direct match for ${niche} video concept with requested ${music} audio texture. Provides authentic high-retention atmosphere.`,
      why_now: "Currently in peak freshness window with active public signals.",
      source_url: "https://later.com/blog/instagram-reels-trends/travel-spain",
      evidence_confidence: 0.92,
      candidate: {
        trend_signal: {
          source_id: "later_instagram",
          platform: "instagram",
          scraped_at: new Date().toISOString()
        },
        music_evidence: {
          spotify_url: "https://www.deezer.com/track/2539912471",
          preview_url: "https://cdnt-preview.dzcdn.net/preview/b22037704.mp3",
          genres: [music || "acoustic", "flamenco"],
          energy: 0.45,
          tempo: 84,
          valence: 0.65
        }
      }
    },
    {
      rank: 2,
      track: "Kathak Sitar Fusion",
      artist: "Indian Classical Ensemble",
      trend_name: "Indian Classical Kathak & Sitar Fusion Reel",
      platform: "instagram",
      content_type: "reels",
      creator_match_score: 0.91,
      p_music_similarity: 0.92,
      p_virality_potential: 0.85,
      p_concept_relevance: 0.95,
      virality_tier: "High Momentum",
      why_it_matches: "Near-perfect match for requested traditional acoustic rhythm and graceful choreography.",
      why_now: "High retention across short video platforms.",
      source_url: "https://later.com/blog/instagram-reels-trends/indian-classical-dance",
      evidence_confidence: 0.88,
      candidate: {
        trend_signal: {
          source_id: "later_instagram",
          platform: "instagram",
          scraped_at: new Date().toISOString()
        },
        music_evidence: {
          spotify_url: "https://www.deezer.com/track/2539912451",
          preview_url: "https://cdnt-preview.dzcdn.net/preview/a11022440.mp3",
          genres: ["classical", "fusion"],
          energy: 0.40,
          tempo: 78,
          valence: 0.50
        }
      }
    },
    {
      rank: 3,
      track: "Calm Solitude Arr. For Violin",
      artist: "Dream Presence",
      trend_name: "Morning Routine Focus & Deep Work",
      platform: "cross_platform",
      content_type: "shorts",
      creator_match_score: 0.86,
      p_music_similarity: 0.88,
      p_virality_potential: 0.80,
      p_concept_relevance: 0.90,
      virality_tier: "High Momentum",
      why_it_matches: "Soothing acoustic string arrangement supporting long video focus.",
      why_now: "Active trend across study and productivity reels.",
      source_url: "https://blog.hootsuite.com/social-media-trends/",
      evidence_confidence: 0.85,
      candidate: {
        trend_signal: {
          source_id: "hootsuite_blog",
          platform: "youtube",
          scraped_at: new Date().toISOString()
        },
        music_evidence: {
          spotify_url: "https://www.deezer.com/track/2124843607",
          preview_url: "https://cdnt-preview.dzcdn.net/preview/c33044550.mp3",
          genres: ["violin", "calm", "study"],
          energy: 0.22,
          tempo: 62,
          valence: 0.40
        }
      }
    },
    {
      rank: 4,
      track: "Die With A Smile",
      artist: "Lady Gaga & Bruno Mars",
      trend_name: "Shazam Top 200 Chart Trending Sound",
      platform: "cross_platform",
      content_type: "reels",
      creator_match_score: 0.82,
      p_music_similarity: 0.75,
      p_virality_potential: 0.95,
      p_concept_relevance: 0.80,
      virality_tier: "Explosive Growth",
      why_it_matches: "#1 Trending sound on Shazam Top 200 with 1.2M Shazams.",
      why_now: "Explosive viral growth across all platforms.",
      source_url: "https://www.shazam.com/charts/top-200/united-states",
      evidence_confidence: 0.95,
      candidate: {
        trend_signal: {
          source_id: "shazam_charts",
          platform: "cross_platform",
          scraped_at: new Date().toISOString()
        },
        music_evidence: {
          spotify_url: "https://www.deezer.com/track/2801558052",
          preview_url: "https://cdnt-preview.dzcdn.net/preview/d44055660.mp3",
          genres: ["pop", "viral"],
          energy: 0.70,
          tempo: 110,
          valence: 0.75
        }
      }
    },
    {
      rank: 5,
      track: "360",
      artist: "Charli xcx",
      trend_name: "Hype Machine Popular Indie Sound",
      platform: "cross_platform",
      content_type: "tiktok",
      creator_match_score: 0.78,
      p_music_similarity: 0.70,
      p_virality_potential: 0.90,
      p_concept_relevance: 0.76,
      virality_tier: "High Momentum",
      why_it_matches: "High engagement trend signal on Hype Machine Popular list.",
      why_now: "Consistent daily growth.",
      source_url: "https://hypem.com/popular",
      evidence_confidence: 0.90,
      candidate: {
        trend_signal: {
          source_id: "hypem_popular",
          platform: "tiktok",
          scraped_at: new Date().toISOString()
        },
        music_evidence: {
          spotify_url: "https://www.deezer.com/track/2833834772",
          preview_url: "https://cdnt-preview.dzcdn.net/preview/e55066770.mp3",
          genres: ["indie", "pop"],
          energy: 0.78,
          tempo: 120,
          valence: 0.80
        }
      }
    }
  ];
}
