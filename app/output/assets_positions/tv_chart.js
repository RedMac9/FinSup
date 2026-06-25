// Render glue between Dash and TradingView Lightweight Charts (v4).
// A Dash clientside callback calls window.dash_clientside.tvchart.render(data)
// whenever the dcc.Store payload changes.
//
// Payload shape:
//   {
//     chartType: "candlestick" | "line",
//     priceSeries: [ { ticker, type, color, data:[...] }, ... ],
//     indicators:  [ { ticker, title, pane, type, color, data:[...] }, ... ]
//   }
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

    function addIndicator(state, ind) {
        if (ind.type === "markers") {
            var target = state.priceByTicker[ind.ticker];
            if (target && ind.data && ind.data.length) {
                target.setMarkers(ind.data);
            }
            return;
        }

        var opts = { color: ind.color, lineWidth: 2, priceLineVisible: false, lastValueVisible: false };
        // Main-pane indicators ride the normalized % scale; separate panes keep their own.
        if (ind.pane !== "separate") { assign(opts, percentFormat(state.normalized)); }
        var series;
        if (ind.pane === "separate") {
            // Own price scale, parked in the lower portion to mimic a sub-pane.
            var scaleId = "pane_" + ind.title;
            opts.priceScaleId = scaleId;
            series = (ind.type === "histogram")
                ? state.chart.addHistogramSeries(opts)
                : state.chart.addLineSeries(opts);
            state.chart.priceScale(scaleId).applyOptions({
                scaleMargins: { top: 0.78, bottom: 0 },
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

        priceSeries.forEach(function (ps) { addPriceSeries(state, ps, multi); });
        ((data && data.indicators) || []).forEach(function (ind) { addIndicator(state, ind); });
        updateLegend(el, priceSeries, multi);

        return noUpdate;
    }

    window.dash_clientside.tvchart = { render: render };
})();
