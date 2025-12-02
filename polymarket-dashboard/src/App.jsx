import React, { useEffect, useMemo, useRef, useState } from "react";

/**
 * Polymarket Paper Trading – Hourly BTC Up/Down Dashboard (No Wallet)
 * 
 * Paste any Polymarket event URL like:
 * https://polymarket.com/event/bitcoin-up-or-down-october-29-1am-et?tid=1761714186437
 *
 * Shows (auto-refreshed):
 *  - current price (BTCUSDT last price on Binance)
 *  - price to beat (open of the target 1H candle on Binance per market start time)
 *  - difference (curr - priceToBeat)
 *  - time remaining to market resolution (start + 1h - now)
 *  - current UP price & current DOWN price (best BUY price for each outcome via CLOB /price)
 *
 * No wallets, no orders – data-only. Designed for paper trading logic to be added later.
 *
 * Notes:
 *  - Uses Gamma API to resolve the market from URL (via slug or tid).
 *  - If a `tid` query param is present, we resolve the exact market quickly.
 *  - Otherwise, we fetch the event by slug then pick the most relevant market (first).
 *  - Handles hourly markets where each hour is a separate market under one event.
 */

// APIs
const GAMMA_BASE = "https://gamma-api.polymarket.com"; // metadata
const CLOB_BASE = "https://clob.polymarket.com";       // price quotes, books
const BINANCE_BASE = "https://api.binance.com";         // spot/kline

// Helpers
function parsePolymarketUrl(inputUrl) {
  try {
    const u = new URL(inputUrl);
    const parts = u.pathname.split("/").filter(Boolean);
    const idx = parts.findIndex((p) => p === "event");
    const slug = idx >= 0 && parts[idx + 1] ? parts[idx + 1] : null; // event slug
    const tid = u.searchParams.get("tid");
    return { slug, tid };
  } catch (e) {
    return { slug: null, tid: null };
  }
}

function formatUSD(x) {
  if (x == null || isNaN(Number(x))) return "–";
  return `$${Number(x).toFixed(2)}`;
}

function formatProb(x) {
  if (x == null || isNaN(Number(x))) return "–";
  // CLOB prices are in dollars 0.00–1.00; show as cents too
  return `${(Number(x) * 100).toFixed(1)}%`;
}

function msUntil(dateIso, plusMs = 0) {
  const now = Date.now();
  const end = new Date(dateIso).getTime() + plusMs;
  return Math.max(0, end - now);
}

function formatHMS(ms) {
  const s = Math.floor(ms / 1000);
  const hh = Math.floor(s / 3600);
  const mm = Math.floor((s % 3600) / 60);
  const ss = s % 60;
  return `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
}

export default function App() {
  const [eventUrl, setEventUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Core market data we resolve from Gamma/CLOB
  const [market, setMarket] = useState(null); // gamma market payload
  const [tokens, setTokens] = useState(null); // { up: tokenId, down: tokenId }
  const [upPrice, setUpPrice] = useState(null); // BUY price (best ask) in $ (0-1)
  const [downPrice, setDownPrice] = useState(null);

  // Binance
  const [btcSpot, setBtcSpot] = useState(null); // current BTCUSDT
  const [priceToBeat, setPriceToBeat] = useState(null); // hourly candle open

  // Countdown timer
  const [remainingMs, setRemainingMs] = useState(0);

  const pollRef = useRef({});

  // Resolve and load data for a given URL
  async function handleLoad(url) {
    setError("");
    setLoading(true);
    try {
      const { slug, tid } = parsePolymarketUrl(url);
      if (!slug && !tid) throw new Error("Geçerli bir Polymarket event URL'si girin.");

      // Step 1: find the specific market and its clob token ids
      let mkt = null;
      if (tid) {
        // Fetch the market containing this token id (fast path)
        const resp = await fetch(`${GAMMA_BASE}/markets?clob_token_ids=${encodeURIComponent(tid)}`);
        const list = await resp.json();
        if (!Array.isArray(list) || list.length === 0) throw new Error("Market bulunamadı (tid).");
        mkt = list[0];
      } else if (slug) {
        // Fetch the event and take the first market as a fallback
        const ev = await (await fetch(`${GAMMA_BASE}/events/slug/${slug}`)).json();
        if (!ev || !Array.isArray(ev.markets) || ev.markets.length === 0) throw new Error("Etkinlikte market bulunamadı.");
        // Heuristic: choose the market that is currently accepting orders or the nearest startDate
        mkt = ev.markets.sort((a, b) => new Date(a.startDateIso || a.startDate || 0) - new Date(b.startDateIso || b.startDate || 0))[0];
      }

      // Parse tokens & outcomes -> identify UP/DOWN
      const clobTokenIds = (mkt.clobTokenIds || mkt.clob_token_ids || "").split(",").map((s) => s.trim()).filter(Boolean);
      const outcomes = (mkt.outcomes || mkt.shortOutcomes || "").split(",").map((s) => s.trim());

      // Map outcome names to token ids (assuming 2-outcome market)
      let upToken = null, downToken = null;
      outcomes.forEach((name, idx) => {
        const tokenId = clobTokenIds[idx];
        if (!tokenId) return;
        if ((name || "").toLowerCase().includes("up")) upToken = tokenId;
        if ((name || "").toLowerCase().includes("down")) downToken = tokenId;
      });
      // Fallback if names missing – just set by index
      if (!upToken && clobTokenIds[0]) upToken = clobTokenIds[0];
      if (!downToken && clobTokenIds[1]) downToken = clobTokenIds[1];

      setMarket(mkt);
      setTokens({ up: upToken, down: downToken });

      // Step 2: compute time remaining to end of the hour (startDate + 1h)
      const startIso = mkt.startDateIso || mkt.startDate || mkt.gameStartTime;
      if (startIso) {
        const remain = msUntil(startIso, 60 * 60 * 1000);
        setRemainingMs(remain);
      }

      // Step 3: load prices immediately
      fetchAllPrices({ upToken: upToken, downToken: downToken }, startIso);

      // Start polling every 3s
      clearInterval(pollRef.current.timer);
      pollRef.current.timer = setInterval(() => fetchAllPrices({ upToken, downToken }, startIso), 3000);

      // Start countdown ticker (1s)
      clearInterval(pollRef.current.countdown);
      pollRef.current.countdown = setInterval(() => {
        const ms = startIso ? msUntil(startIso, 60 * 60 * 1000) : 0;
        setRemainingMs(ms);
      }, 1000);

    } catch (e) {
      console.error(e);
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  async function fetchAllPrices({ upToken, downToken }, startIso) {
    try {
      // 1) Binance BTCUSDT last price
      const spot = await (await fetch(`${BINANCE_BASE}/api/v3/ticker/price?symbol=BTCUSDT`)).json();
      const last = Number(spot?.price);
      setBtcSpot(isFinite(last) ? last : null);

      // 2) Price to beat = open of the 1H kline starting at startIso
      if (startIso) {
        const startMs = new Date(startIso).getTime();
        const endMs = startMs + 60 * 60 * 1000; // +1h window
        const kline = await (await fetch(`${BINANCE_BASE}/api/v3/klines?symbol=BTCUSDT&interval=1h&startTime=${startMs}&endTime=${endMs}&limit=1`)).json();
        if (Array.isArray(kline) && kline.length > 0) {
          const open = Number(kline[0][1]); // [openTime, open, high, low, close, ...]
          setPriceToBeat(isFinite(open) ? open : null);
        }
      }

      // 3) Outcome prices (best BUY quote) from CLOB
      if (upToken) {
        const up = await (await fetch(`${CLOB_BASE}/price?token_id=${encodeURIComponent(upToken)}&side=BUY`)).json();
        const val = Number(up?.price);
        setUpPrice(isFinite(val) ? val : null);
      }
      if (downToken) {
        const dp = await (await fetch(`${CLOB_BASE}/price?token_id=${encodeURIComponent(downToken)}&side=BUY`)).json();
        const val2 = Number(dp?.price);
        setDownPrice(isFinite(val2) ? val2 : null);
      }
    } catch (e) {
      console.warn("fetchAllPrices error", e);
    }
  }

  useEffect(() => {
    return () => {
      clearInterval(pollRef.current.timer);
      clearInterval(pollRef.current.countdown);
    };
  }, []);

  const diff = useMemo(() => {
    if (btcSpot == null || priceToBeat == null) return null;
    return btcSpot - priceToBeat;
  }, [btcSpot, priceToBeat]);

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <header className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Polymarket – BTC Up/Down (Paper)</h1>
          <span className="text-xs opacity-70">No wallet • Data-only • Refresh ~3s</span>
        </header>

        {/* URL input */}
        <div className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-4">
          <label className="block text-sm mb-2">Polymarket Event URL</label>
          <div className="flex gap-2">
            <input
              value={eventUrl}
              onChange={(e) => setEventUrl(e.target.value)}
              placeholder="Paste Polymarket event URL (hourly BTC Up/Down)"
              className="flex-1 bg-neutral-950 border border-neutral-800 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <button
              onClick={() => handleLoad(eventUrl)}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-sm font-medium"
              disabled={loading}
            >
              {loading ? "Loading…" : "Load"}
            </button>
          </div>
          {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
        </div>

        {/* Market summary */}
        {market && (
          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-4 space-y-1">
              <div className="text-sm opacity-70">Market</div>
              <div className="text-lg font-medium">{market?.question || market?.slug || "BTC Up or Down"}</div>
              <div className="text-xs opacity-60">
                Start: {new Date(market.startDateIso || market.startDate || market.gameStartTime).toLocaleString()} • End: {new Date(new Date(market.startDateIso || market.startDate || market.gameStartTime).getTime() + 3600000).toLocaleString()}
              </div>
            </div>
            <div className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-4 grid grid-cols-2 gap-2 text-sm">
              <div>
                <div className="opacity-60">Time Remaining</div>
                <div className="text-xl font-semibold">{formatHMS(remainingMs)}</div>
              </div>
              <div>
                <div className="opacity-60">Resolution Source</div>
                <div className="font-mono">Binance BTC/USDT</div>
              </div>
            </div>
          </div>
        )}

        {/* Prices */}
        <div className="grid md:grid-cols-3 gap-4">
          <div className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-4">
            <div className="text-sm opacity-60">Current BTC Price</div>
            <div className="text-2xl font-semibold">{btcSpot ? formatUSD(btcSpot) : "–"}</div>
          </div>
          <div className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-4">
            <div className="text-sm opacity-60">Price to Beat (Open of Hour)</div>
            <div className="text-2xl font-semibold">{priceToBeat ? formatUSD(priceToBeat) : "–"}</div>
          </div>
          <div className={`bg-neutral-900/60 border border-neutral-800 rounded-2xl p-4 ${diff != null ? (diff >= 0 ? "ring-1 ring-green-600/40" : "ring-1 ring-red-600/40") : ""}`}>
            <div className="text-sm opacity-60">Difference (Curr − Open)</div>
            <div className="text-2xl font-semibold">{diff == null ? "–" : `${diff >= 0 ? "+" : ""}${diff.toFixed(2)}`}</div>
          </div>
        </div>

        {/* Outcome quotes */}
        <div className="grid md:grid-cols-2 gap-4">
          <div className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm opacity-60">Current UP Price (BUY)</div>
                <div className="text-2xl font-semibold">{upPrice != null ? formatUSD(upPrice) : "–"}</div>
              </div>
              <div className="text-sm opacity-60">{upPrice != null ? formatProb(upPrice) : ""}</div>
            </div>
          </div>
          <div className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm opacity-60">Current DOWN Price (BUY)</div>
                <div className="text-2xl font-semibold">{downPrice != null ? formatUSD(downPrice) : "–"}</div>
              </div>
              <div className="text-sm opacity-60">{downPrice != null ? formatProb(downPrice) : ""}</div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="text-xs opacity-60">
          Data: Gamma Markets API, CLOB /price, Binance BTCUSDT. Paste a new hourly URL as it changes.
        </div>
      </div>
    </div>
  );
}
