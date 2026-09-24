// Render glue between Dash and TradingView Lightweight Charts (v4).
// A Dash clientside callback calls window.dash_clientside.tvchart.render(data)
// whenever the dcc.Store payload changes.
//
// Payload shape:
//   {
//     chartType: "candlestick" | "line",
//     priceSeries: [ { ticker, type, color, data:[...] }, ... ],
//     indicators:  [ { ticker, indicator, title, pane, type, color, data:[...] }, ... ]
//   }
//   type "band" -> data:[{start, end, top, bottom, color, label}] drawn as shaded
//   rectangles attached to that ticker's price series (see BandsPrimitive).
//
// The chart instance is created once per container and cached on the DOM node so
// changing selection / indicators preserves the user's zoom & pan.

window.dash_clientside = window.dash_clientside || {};

(function () {
    var ELEMENT_ID = "tv-chart";
    var CANDLE_UP = "#26a69a";
    var CANDLE_DOWN = "#ef5350";

    function buildChart(el) {
        // autoSize lets the library track the container internally. Sizing it
        // manually creates a resize feedback loop that makes the chart creep.
        return LightweightCharts.createChart(el, {
            autoSize: true,
            layout: { background: { color: "#ffffff" }, textColor: "#1e293b" },
            grid: {
                vertLines: { color: "#eef2f7" },
                horzLines: { color: "#eef2f7" },
            },
            rightPriceScale: { borderColor: "#cbd5e1" },
            timeScale: { borderColor: "#cbd5e1", timeVisible: false },
            crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        });
    }

    function ensureLegend(el) {
        var legend = el.querySelector(".pos-legend");
        if (!legend) {
            legend = document.createElement("div");
            legend.className = "pos-legend";
            el.appendChild(legend);
        }
        return legend;
    }

    function updateLegend(el, priceSeries, multi) {
        var legend = ensureLegend(el);
        legend.innerHTML = "";
        (priceSeries || []).forEach(function (ps) {
            var swatch = (ps.type === "candlestick" && !multi) ? CANDLE_UP : ps.color;
            var item = document.createElement("span");
            item.className = "pos-legend-item";
            item.innerHTML =
                '<span class="pos-legend-dot" style="background:' + swatch + '"></span>' +
                ps.ticker;
            legend.appendChild(item);
        });
        legend.style.display = (priceSeries && priceSeries.length) ? "flex" : "none";
    }

    function clearSeries(state) {
        (state.allSeries || []).forEach(function (s) {
            try { state.chart.removeSeries(s); } catch (e) { /* already gone */ }
        });
        state.allSeries = [];
        state.priceByTicker = {};
        state.priceList = [];
        state.pendingMarkers = {};
    }

    function ensureTooltip(el) {
        var tip = el.querySelector(".pos-tooltip");
        if (!tip) {
            tip = document.createElement("div");
            tip.className = "pos-tooltip";
            tip.style.display = "none";
            el.appendChild(tip);
        }
        return tip;
    }

    // Show the ticker (and value) of the price line nearest the cursor.
    function setupTooltip(el, state) {
        var tip = ensureTooltip(el);
        state.chart.subscribeCrosshairMove(function (param) {
            if (!param || !param.point || !param.time || !state.priceList.length) {
                tip.style.display = "none";
                return;
            }
            var best = null, bestDist = Infinity, bestVal = null;
            state.priceList.forEach(function (entry) {
                var sd = param.seriesData.get(entry.series);
                if (!sd) return;
                var val = (sd.value !== undefined) ? sd.value : sd.close;
                if (val === undefined) return;
                var y = entry.series.priceToCoordinate(val);
                if (y === null) return;
                var dist = Math.abs(y - param.point.y);
                if (dist < bestDist) { bestDist = dist; best = entry; bestVal = val; }
            });
            if (!best || bestDist > 36) { tip.style.display = "none"; return; }

            var suffix = state.normalized ? "%" : "";
            tip.innerHTML =
                '<span class="pos-tooltip-dot" style="background:' + best.swatch + '"></span>' +
                '<b>' + best.ticker + '</b> ' + bestVal.toFixed(2) + suffix;
            tip.style.display = "block";
            var x = param.point.x + 14, y = param.point.y + 14;
            tip.style.left = Math.min(x, el.clientWidth - tip.offsetWidth - 6) + "px";
            tip.style.top = Math.min(y, el.clientHeight - tip.offsetHeight - 6) + "px";
        });
    }

    function percentFormat(normalized) {
        return normalized ? { priceFormat: { type: "percent" } } : {};
    }

    function assign(target, extra) {
        for (var k in extra) { if (extra.hasOwnProperty(k)) target[k] = extra[k]; }
        return target;
    }

    function addPriceSeries(state, ps, multi) {
        var series;
        if (ps.type === "line") {
            series = state.chart.addLineSeries(assign({
                color: ps.color, lineWidth: 2, priceLineVisible: false, lastValueVisible: false,
            }, percentFormat(state.normalized)));
        } else {
            var c = multi ? ps.color : null;
            series = state.chart.addCandlestickSeries(c ? {
                upColor: c, downColor: c, borderVisible: false, wickUpColor: c, wickDownColor: c,
            } : {
                upColor: CANDLE_UP, downColor: CANDLE_DOWN, borderVisible: false,
                wickUpColor: CANDLE_UP, wickDownColor: CANDLE_DOWN,
            });
        }
        series.setData(ps.data || []);
        state.allSeries.push(series);
        state.priceByTicker[ps.ticker] = series;
        var swatch = (ps.type === "candlestick" && !multi) ? CANDLE_UP : ps.color;
        state.priceList.push({ ticker: ps.ticker, series: series, swatch: swatch, type: ps.type });
    }

    // --- Bands (DiNapoli zones): shaded rectangles via the v4.1+ series
    // primitive API. Each band starts at its own date and runs to the right
    // edge of the pane, like the zones on the strategy document's charts.
    function hexToRgba(hex, alpha) {
        var h = (hex || "#64748b").replace("#", "");
        if (h.length === 3) { h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2]; }
        var n = parseInt(h, 16);
        return "rgba(" + ((n >> 16) & 255) + "," + ((n >> 8) & 255) + "," + (n & 255) + "," + alpha + ")";
    }

    function BandsPrimitive(bands, opacity) {
        var self = this;
        this._bands = bands || [];
        this._opacity = (opacity === undefined) ? 0.18 : opacity;
        this._chart = null;
        this._series = null;
        this._view = {
            zOrder: function () { return "bottom"; },
            renderer: function () { return { draw: function (target) { self._draw(target); } }; },
        };
    }
    BandsPrimitive.prototype.attached = function (p) { this._chart = p.chart; this._series = p.series; };
    BandsPrimitive.prototype.detached = function () { this._chart = null; this._series = null; };
    BandsPrimitive.prototype.updateAllViews = function () {};
    BandsPrimitive.prototype.paneViews = function () { return [this._view]; };
    BandsPrimitive.prototype._draw = function (target) {
        var chart = this._chart, series = this._series, bands = this._bands, opacity = this._opacity;
        if (!chart || !series) return;
        var ts = chart.timeScale();
        target.useBitmapCoordinateSpace(function (scope) {
            var ctx = scope.context, hr = scope.horizontalPixelRatio, vr = scope.verticalPixelRatio;
            var right = scope.bitmapSize.width;
            bands.forEach(function (b) {
                var yTop = series.priceToCoordinate(b.top);
                var yBot = series.priceToCoordinate(b.bottom);
                if (yTop === null || yBot === null) return;
                var x0 = ts.timeToCoordinate(b.start);
                if (x0 === null) x0 = 0;   // start is off the loaded data -> left edge
                var y0 = Math.min(yTop, yBot) * vr;
                var h = Math.max(Math.abs(yBot - yTop) * vr, 2 * vr);
                var x = Math.max(0, x0 * hr);
                ctx.fillStyle = hexToRgba(b.color, opacity);
                ctx.fillRect(x, y0, right - x, h);
                ctx.fillStyle = hexToRgba(b.color, 0.95);
                ctx.font = (11 * vr) + "px sans-serif";
                ctx.fillText(b.label || "", x + 4 * hr, y0 - 3 * vr);
            });
        });
    };

    // Sub-panes: Lightweight Charts v4 has no real panes, so every indicator
    // with pane === "separate" gets its own price scale squeezed into a
    // horizontal strip at the bottom; strips are stacked, never overlapped,
    // and the main price scale is shrunk to leave room for them.
    function layoutPanes(state, indicators) {
        var keys = [];
        (indicators || []).forEach(function (ind) {
            if (ind.pane !== "separate") return;
            var key = paneKey(ind);
            if (keys.indexOf(key) < 0) keys.push(key);
        });
        var n = keys.length;
        var strip = n ? Math.min(0.2, 0.45 / n) : 0;
        state.paneMargins = {};
        keys.forEach(function (key, i) {
            // i = 0 is the top-most strip.
            state.paneMargins[key] = {
                top: 1 - (n - i) * strip + 0.01,
                bottom: (n - i - 1) * strip,
            };
        });
        state.chart.priceScale("right").applyOptions({
            scaleMargins: { top: 0.05, bottom: n ? n * strip + 0.03 : 0.08 },
        });
    }

    function paneKey(ind) {
        // One strip per indicator per ticker (volume of two tickers has
        // different scales, so they must not share a price scale).
        return "pane_" + (ind.ticker || "") + "_" + (ind.indicator || ind.title);
    }

    function addIndicator(state, ind) {
        if (ind.type === "band") {
            var host = state.priceByTicker[ind.ticker];
            if (host && host.attachPrimitive && ind.data && ind.data.length) {
                host.attachPrimitive(new BandsPrimitive(ind.data, ind.opacity));
            }
            return;
        }
        if (ind.type === "markers") {
            // Several marker-producing indicators can target the same ticker
            // (e.g. "EMA32 cross" + "DiNapoli setups"); setMarkers() replaces
            // a series' markers wholesale, so accumulate here and flush once
            // per ticker after all indicators have been processed.
            if (ind.data && ind.data.length) {
                var list = state.pendingMarkers[ind.ticker] || [];
                state.pendingMarkers[ind.ticker] = list.concat(ind.data);
            }
            return;
        }

        var opts = { color: ind.color, lineWidth: 2, priceLineVisible: false, lastValueVisible: false };
        // Main-pane indicators ride the normalized % scale; separate panes keep their own.
        if (ind.pane !== "separate") { assign(opts, percentFormat(state.normalized)); }
        var series;
        if (ind.pane === "separate") {
            // Own price scale, parked in its strip (see layoutPanes).
            var scaleId = paneKey(ind);
            opts.priceScaleId = scaleId;
            if (ind.type === "histogram") { delete opts.lineWidth; }
            if (ind.indicator === "Volume") { opts.priceFormat = { type: "volume" }; }
            series = (ind.type === "histogram")
                ? state.chart.addHistogramSeries(opts)
                : state.chart.addLineSeries(assign(opts, { lineWidth: 1 }));
            state.chart.priceScale(scaleId).applyOptions({
                scaleMargins: state.paneMargins[scaleId] || { top: 0.78, bottom: 0 },
                borderColor: "#cbd5e1",
            });
        } else {
            series = (ind.type === "histogram")
                ? state.chart.addHistogramSeries(opts)
                : state.chart.addLineSeries(opts);
        }
        series.setData(ind.data || []);
        state.allSeries.push(series);
    }

    function render(data) {
        var noUpdate = (window.dash_clientside && window.dash_clientside.no_update) || undefined;
        if (typeof LightweightCharts === "undefined") {
            requestAnimationFrame(function () { render(data); });
            return noUpdate;
        }
        var el = document.getElementById(ELEMENT_ID);
        if (!el) {
            requestAnimationFrame(function () { render(data); });
            return noUpdate;
        }

        var state = el._tvState;
        if (!state) {
            state = el._tvState = { chart: buildChart(el), allSeries: [], priceByTicker: {}, priceList: [] };
            setupTooltip(el, state);
        }

        var priceSeries = (data && data.priceSeries) || [];
        var multi = priceSeries.length > 1;
        state.normalized = !!(data && data.normalized);

        clearSeries(state);

        if (!priceSeries.length) {
            updateLegend(el, [], multi);
            return noUpdate;
        }

        var indicators = (data && data.indicators) || [];
        layoutPanes(state, indicators);
        priceSeries.forEach(function (ps) { addPriceSeries(state, ps, multi); });
        indicators.forEach(function (ind) { addIndicator(state, ind); });
        Object.keys(state.pendingMarkers || {}).forEach(function (ticker) {
            var target = state.priceByTicker[ticker];
            if (!target) return;
            var merged = state.pendingMarkers[ticker].slice().sort(function (a, b) {
                return a.time < b.time ? -1 : (a.time > b.time ? 1 : 0);
            });
            target.setMarkers(merged);
        });
        updateLegend(el, priceSeries, multi);

        return noUpdate;
    }

    window.dash_clientside.tvchart = { render: render };
})();
