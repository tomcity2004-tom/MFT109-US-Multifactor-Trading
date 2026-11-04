# Phase 10A — Daily-return distribution diagnostics

Sample: 2016-01-05 through 2025-12-31; 2,513 paired daily returns. The initial accounting anchor is excluded consistently with Phase 6. Genuine cash-day zeros and all extremes are retained.

**Strategy:** mean daily return 0.083366%, median 0.118532%, sample daily SD 1.452504%, minimum -12.362296%, maximum 13.205530%; skewness -0.226640 (left asymmetry), Fisher excess kurtosis 10.151643. Positive excess kurtosis indicates greater extreme-tail influence than a normal reference in this sample. Jarque–Bera = 10764.357409, p-value = numerical underflow below floating-point resolution, log p-value = -5382.178704; alpha = 0.05: **Reject H0**.

**SPY:** mean daily return 0.061655%, median 0.073115%, sample daily SD 1.134352%, minimum -10.942366%, maximum 10.501940%; skewness -0.320631 (left asymmetry), Fisher excess kurtosis 14.732943. Positive excess kurtosis indicates greater extreme-tail influence than a normal reference in this sample. Jarque–Bera = 22673.307197, p-value = numerical underflow below floating-point resolution, log p-value = -11336.653598; alpha = 0.05: **Reject H0**.

Compared with SPY, the strategy has higher mean daily return and higher daily volatility. Its reported excess kurtosis is lower. These sample comparisons do not establish causality or future superiority.

Statistics are daily, not annualized. CSV location/scale/quantile values are decimals (0.01 = 1%); skewness and excess kurtosis are dimensionless. Sample SD uses ddof=1; reported skewness and Fisher excess kurtosis use bias=False. Jarque–Bera uses the standard biased central-moment estimators internally, not those adjusted table estimates.

Histograms use common Freedman–Diaconis bins spanning both complete samples and density normalization. The normal PDF uses each sample's mean and sample SD; it is a visual reference, not an assertion of normality. Q-Q plots retain every observation and use SciPy normal order-statistic quantiles with a fitted reference line. Extremes may compress the central histogram; none are clipped, winsorized or removed.

Jarque–Bera is an asymptotic diagnostic of skewness and kurtosis. Financial returns can exhibit serial dependence and volatility clustering, limiting textbook p-value calibration; large samples also detect small departures. Rejecting normality does not invalidate the backtest or establish strategy quality or causality. Failing to reject does not prove normality. The fixed current S&P 500 universe retains survivorship bias. These descriptive results do not change any strategy parameter or validated result.
