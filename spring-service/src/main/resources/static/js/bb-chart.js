/*
 * bb-chart.js
 * Real Candlestick + Bollinger Bands + Volume
 */

(function () {
    'use strict';

    // =========================================================
    // CDN
    // =========================================================

    const DEPENDENCIES = {
        chart:
            'https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js',

        luxon:
            'https://cdn.jsdelivr.net/npm/luxon@3.6.1/build/global/luxon.min.js',

        adapter:
            'https://cdn.jsdelivr.net/npm/chartjs-adapter-luxon@1.3.1/dist/chartjs-adapter-luxon.umd.min.js',

        financial:
            'https://cdn.jsdelivr.net/npm/chartjs-chart-financial@0.2.1/dist/chartjs-chart-financial.min.js'
    };

    let readyPromise = null;


    // =========================================================
    // LOAD SCRIPT
    // =========================================================

    function loadScript(src, id) {
        return new Promise((resolve, reject) => {

            if (id && document.getElementById(id)) {
                resolve();
                return;
            }

            const script = document.createElement('script');

            if (id) {
                script.id = id;
            }

            script.src = src;
            script.async = false;

            script.onload = () => {
                console.log('[BB Chart] Loaded:', src);
                resolve();
            };

            script.onerror = () => {
                reject(
                    new Error('Không thể tải thư viện: ' + src)
                );
            };

            document.head.appendChild(script);
        });
    }


    // =========================================================
    // WAIT FOR CHART.JS
    // =========================================================

    function waitForChartJS(timeout = 10000) {

        return new Promise((resolve, reject) => {

            const start = Date.now();

            function check() {

                if (window.Chart) {
                    resolve(window.Chart);
                    return;
                }

                if (Date.now() - start >= timeout) {
                    reject(
                        new Error(
                            'Chart.js chưa được tải.'
                        )
                    );
                    return;
                }

                setTimeout(check, 50);
            }

            check();
        });
    }


    // =========================================================
    // CHECK FINANCIAL CONTROLLER
    // =========================================================

    function hasFinancialController() {

        if (!window.Chart || !window.Chart.registry) {
            return false;
        }

        try {
            return !!window.Chart.registry.getController('candlestick');
        } catch (e) {
            return false;
        }
    }


    // =========================================================
    // ENSURE EVERYTHING IS READY
    // =========================================================

    async function ensureBollingerChartReady() {

        if (readyPromise) {return readyPromise;}

        readyPromise = (async () => {

            // =========================================
            // Chart.js
            // =========================================

            if (!window.Chart) {
                await loadScript(
                    DEPENDENCIES.chart,
                    'bb-chart-js'
                );
            }
            await waitForChartJS();

            // =========================================
            // Luxon
            // =========================================

            if (!window.luxon) {
                await loadScript(
                    DEPENDENCIES.luxon,
                    'bb-luxon-js'
                );
            }

            // =========================================
            // Luxon adapter
            // =========================================

            if (!document.getElementById('bb-luxon-adapter-js')) {
                await loadScript(
                    DEPENDENCIES.adapter,
                    'bb-luxon-adapter-js'
                );
            }

            console.log(
                '[BB Chart] Luxon:',
                !!window.luxon
            );

            console.log(
                '[BB Chart] Date adapter script loaded.'
            );

            // =========================================
            // Financial plugin
            // =========================================

            if (!hasFinancialController()) {
                await loadScript(
                    DEPENDENCIES.financial,
                    'bb-financial-js'
                );
            }

            await new Promise(resolve =>
                setTimeout(resolve, 100)
            );

            if (!hasFinancialController()) {
                throw new Error(
                    'Không tìm thấy Candlestick controller của chartjs-chart-financial.'
                );
            }

            console.log(
                '[BB Chart] All dependencies ready.'
            );

            return window.Chart;

        })().catch(error => {

            readyPromise = null;

            console.error(
                '[BB Chart] Initialization failed:',
                error
            );

            throw error;
        });

        return readyPromise;
    }

    // =========================================================
    // NUMBER
    // =========================================================

    function toNumber(value) {

        const n = Number(value);

        return Number.isFinite(n)
            ? n
            : null;
    }


    // =========================================================
    // DATE -> TIMESTAMP
    // =========================================================

    function parseChartDate(value) {

        if (
            value === null ||
            value === undefined ||
            value === ''
        ) {
            return null;
        }


        // Already Date
        if (value instanceof Date) {

            const time = value.getTime();

            return Number.isFinite(time)
                ? time
                : null;
        }


        const text = String(value).trim();


        // YYYY-MM-DD
        const match = text.match(
            /^(\d{4})-(\d{2})-(\d{2})(?:[T\s](.*))?$/
        );


        if (match) {

            const year = Number(match[1]);
            const month = Number(match[2]);
            const day = Number(match[3]);


            // No time -> local midnight
            if (!match[4]) {

                return new Date(
                    year,
                    month - 1,
                    day
                ).getTime();
            }


            const parsed = new Date(text);

            if (!Number.isNaN(parsed.getTime())) {
                return parsed.getTime();
            }


            return new Date(
                year,
                month - 1,
                day
            ).getTime();
        }


        const parsed = new Date(text);

        if (Number.isNaN(parsed.getTime())) {
            return null;
        }

        return parsed.getTime();
    }


    // =========================================================
    // NORMALIZE HISTORY
    // =========================================================

    function normalizeHistory(historyData) {

        if (!Array.isArray(historyData)) {
            return [];
        }


        return historyData

            .map(row => {

                const timestamp = parseChartDate(
                    row.date ??
                    row.Date ??
                    row.datetime ??
                    row.time ??
                    row.timestamp
                );


                const open = toNumber(
                    row.open ?? row.Open
                );

                const high = toNumber(
                    row.high ?? row.High
                );

                const low = toNumber(
                    row.low ?? row.Low
                );

                const close = toNumber(
                    row.close ?? row.Close
                );

                const volume = toNumber(
                    row.volume ?? row.Volume
                ) ?? 0;


                if (
                    timestamp === null ||
                    open === null ||
                    high === null ||
                    low === null ||
                    close === null
                ) {
                    return null;
                }


                return {

                    // IMPORTANT:
                    // timestamp NUMBER, not Date object
                    x: timestamp,

                    o: open,
                    h: high,
                    l: low,
                    c: close,

                    volume: volume
                };

            })

            .filter(Boolean)

            .sort((a, b) => a.x - b.x);
    }


    // =========================================================
    // BOLLINGER
    // =========================================================

    function calculateBollinger(
        candles,
        period = 20,
        multiplier = 2
    ) {

        return candles.map((candle, i) => {

            if (i < period - 1) {

                return {

                    x: candle.x,

                    upper: null,
                    middle: null,
                    lower: null
                };
            }


            const closes = candles

                .slice(
                    i - period + 1,
                    i + 1
                )

                .map(item => item.c);


            const mean =
                closes.reduce(
                    (sum, value) =>
                        sum + value,
                    0
                ) / period;


            const variance =
                closes.reduce(
                    (sum, value) =>
                        sum +
                        Math.pow(
                            value - mean,
                            2
                        ),
                    0
                ) / period;


            const std = Math.sqrt(variance);


            return {

                x: candle.x,

                upper:
                    mean +
                    multiplier * std,

                middle:
                    mean,

                lower:
                    mean -
                    multiplier * std
            };
        });
    }


    // =========================================================
    // DESTROY EXISTING CHART
    // =========================================================

    function destroyChart(canvasId) {

        const canvas =
            document.getElementById(canvasId);

        if (!canvas || !window.Chart) {
            return;
        }


        const existing =
            window.Chart.getChart(canvas);

        if (existing) {
            existing.destroy();
        }
    }


    // =========================================================
    // FORMAT PRICE
    // =========================================================

    function formatPrice(value) {

        if (
            value === null ||
            value === undefined ||
            !Number.isFinite(Number(value))
        ) {
            return '—';
        }


        return Number(value).toLocaleString(
            'vi-VN',
            {
                maximumFractionDigits: 2
            }
        );
    }


    // =========================================================
    // FORMAT DATE
    // =========================================================

    function formatBBDate(value) {

        const timestamp = Number(value);

        if (!Number.isFinite(timestamp)) {
            return '—';
        }


        const date = new Date(timestamp);

        return [

            String(
                date.getDate()
            ).padStart(2, '0'),

            String(
                date.getMonth() + 1
            ).padStart(2, '0'),

            date.getFullYear()

        ].join('-');
    }


    // =========================================================
    // CREATE BOLLINGER CHART
    // =========================================================

    function createBollingerChart(
        canvasId,
        historyData,
        volumeCanvasId
    ) {

        if (!window.Chart) {
            throw new Error(
                'Chart.js chưa sẵn sàng.'
            );
        }


        const canvas =
            document.getElementById(canvasId);


        if (!canvas) {

            throw new Error(
                `Không tìm thấy canvas #${canvasId}.`
            );
        }


        const candles =
            normalizeHistory(historyData);


        if (!candles.length) {

            throw new Error(
                'Không có dữ liệu OHLC hợp lệ để vẽ biểu đồ.'
            );
        }


        console.log(
            '[BB Chart] Candles:',
            candles.length,
            candles[0],
            candles[candles.length - 1]
        );


        const bb =
            calculateBollinger(
                candles,
                20,
                2
            );


        destroyChart(canvasId);


        const chart =
            new Chart(
                canvas.getContext('2d'),
                {

                    type: 'candlestick',

                    data: {

                        datasets: [

                            // =================================
                            // CANDLE
                            // =================================

                            {

                                label: 'Giá',

                                data: candles,

                                yAxisID: 'price',

                                color: {

                                    up: '#198754',

                                    down: '#dc3545',

                                    unchanged: '#6c757d'
                                }
                            },


                            // =================================
                            // BB UPPER
                            // =================================

                            {

                                type: 'line',

                                label: 'BB Upper',

                                data:
                                    bb
                                        .filter(
                                            x =>
                                                x.upper !== null
                                        )
                                        .map(
                                            x => ({
                                                x: x.x,
                                                y: x.upper
                                            })
                                        ),

                                yAxisID: 'price',

                                borderWidth: 1.5,

                                pointRadius: 0,

                                tension: 0.15,

                                fill: false
                            },


                            // =================================
                            // SMA20
                            // =================================

                            {

                                type: 'line',

                                label: 'SMA 20',

                                data:
                                    bb
                                        .filter(
                                            x =>
                                                x.middle !== null
                                        )
                                        .map(
                                            x => ({
                                                x: x.x,
                                                y: x.middle
                                            })
                                        ),

                                yAxisID: 'price',

                                borderWidth: 1.5,

                                pointRadius: 0,

                                tension: 0.15,

                                fill: false
                            },


                            // =================================
                            // BB LOWER
                            // =================================

                            {

                                type: 'line',

                                label: 'BB Lower',

                                data:
                                    bb
                                        .filter(
                                            x =>
                                                x.lower !== null
                                        )
                                        .map(
                                            x => ({
                                                x: x.x,
                                                y: x.lower
                                            })
                                        ),

                                yAxisID: 'price',

                                borderWidth: 1.5,

                                pointRadius: 0,

                                tension: 0.15,

                                fill: false
                            }
                        ]
                    },


                    options: {

                        responsive: true,

                        maintainAspectRatio: false,


                        interaction: {

                            mode: 'index',

                            intersect: false
                        },


                        plugins: {

                            legend: {

                                display: true,

                                position: 'top'
                            },


                            tooltip: {

                                callbacks: {

                                    title: items => {

                                        if (
                                            !items ||
                                            !items.length
                                        ) {
                                            return '';
                                        }

                                        return formatBBDate(
                                            items[0]
                                                .parsed
                                                .x
                                        );
                                    },


                                    label: context => {

                                        const raw =
                                            context.raw;


                                        if (
                                            context.dataset.label ===
                                                'Giá' &&
                                            raw &&
                                            raw.o !== undefined
                                        ) {

                                            return [

                                                `Mở cửa: ${formatPrice(raw.o)}`,

                                                `Cao: ${formatPrice(raw.h)}`,

                                                `Thấp: ${formatPrice(raw.l)}`,

                                                `Đóng cửa: ${formatPrice(raw.c)}`
                                            ];
                                        }


                                        return (
                                            `${context.dataset.label}: ` +
                                            formatPrice(
                                                context.parsed.y
                                            )
                                        );
                                    }
                                }
                            }
                        },


                        scales: {

                            // =================================
                            // TIME AXIS
                            // =================================

                            x: {

                                type: 'time',

                                time: {

                                    unit: 'day',

                                    displayFormats: {

                                        day: 'dd-MM-yyyy'
                                    },

                                    tooltipFormat:
                                        'dd-MM-yyyy'
                                },


                                ticks: {

                                    maxRotation: 0,

                                    autoSkip: true,

                                    maxTicksLimit: 10
                                },


                                grid: {

                                    display: false
                                }
                            },


                            // =================================
                            // PRICE
                            // =================================

                            price: {

                                position: 'left',

                                ticks: {

                                    callback: value =>
                                        formatPrice(value)
                                }
                            }
                        }
                    }
                }
            );


        // =============================================
        // VOLUME
        // =============================================

        if (volumeCanvasId) {

            createVolumeChart(
                volumeCanvasId,
                candles
            );
        }


        return chart;
    }


    // =========================================================
    // VOLUME CHART
    // =========================================================

    function createVolumeChart(
        canvasId,
        candles
    ) {

        const canvas =
            document.getElementById(canvasId);


        if (!canvas) {
            return null;
        }


        destroyChart(canvasId);


        return new Chart(
            canvas.getContext('2d'),
            {

                type: 'bar',

                data: {

                    datasets: [

                        {

                            label: 'Khối lượng',

                            data:
                                candles.map(item => ({

                                    x: item.x,

                                    y: item.volume
                                })),

                            borderWidth: 0
                        }
                    ]
                },


                options: {

                    responsive: true,

                    maintainAspectRatio: false,


                    plugins: {

                        legend: {

                            display: false
                        },


                        tooltip: {

                            callbacks: {

                                title: items => {

                                    if (
                                        !items ||
                                        !items.length
                                    ) {
                                        return '';
                                    }

                                    return formatBBDate(
                                        items[0]
                                            .parsed
                                            .x
                                    );
                                },


                                label: context =>
                                    `Khối lượng: ${
                                        Number(
                                            context.parsed.y || 0
                                        ).toLocaleString('vi-VN')
                                    }`
                            }
                        }
                    },


                    scales: {

                        x: {

                            type: 'time',

                            time: {

                                unit: 'day'
                            },


                            ticks: {

                                display: false
                            },


                            grid: {

                                display: false
                            }
                        },


                        y: {

                            beginAtZero: true,

                            ticks: {

                                callback: value =>
                                    Number(value)
                                        .toLocaleString('vi-VN')
                            }
                        }
                    }
                }
            }
        );
    }


    // =========================================================
    // EXPORT
    // =========================================================

    window.ensureBollingerChartReady =
        ensureBollingerChartReady;

    window.createBollingerChart =
        createBollingerChart;

    window.createVolumeChart =
        createVolumeChart;

    window.calculateBollinger =
        calculateBollinger;

    window.normalizeHistory =
        normalizeHistory;

    window.formatBBDate =
        formatBBDate;

})();