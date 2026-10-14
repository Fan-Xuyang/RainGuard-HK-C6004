const s = require("../../utils/service");
const { nearestNowcast, regionRain } = require("../../utils/core");
Page({
  data: {
    regions: s.regions,
    region: "",
    loading: false,
    sources: [],
    windows: [],
    forecast: [],
    warnings: [],
    rain: "—",
    temperature: "—",
    synopsis: "",
  },
  onShow() {
    clearInterval(this.timer);
    this.refresh();
    this.timer = setInterval(() => this.refresh(), 180000);
  },
  onHide() {
    clearInterval(this.timer);
  },
  onUnload() {
    clearInterval(this.timer);
  },
  onPullDownRefresh() {
    this.refresh().finally(() => wx.stopPullDownRefresh());
  },
  async refresh() {
    if (this.data.loading) return;
    this.setData({ loading: true, region: s.toSimple(s.config().region) });
    try {
      const p = await s.load([
        "rain",
        "weather",
        "warnings",
        "forecast",
        "local",
        "nowcast",
        "tides",
      ]);
      const r = s.regions.find((r) => r.name === s.config().region),
        rain = regionRain(p.weather.data, r.name),
        temp =
          p.weather.data.temperature.data.find((t) => t.place === r.name) ||
          p.weather.data.temperature.data.find((t) => t.place === "香港天文台");
      this.setData({
        rain: s.value(rain && rain.max),
        temperature: s.value(temp && temp.value),
        temperatureLabel: s.toSimple((temp && temp.place) || ""),
        warnings: Object.values(p.warnings.data)
          .filter((x) => x.actionCode !== "CANCEL")
          .map((x) => ({
            name: s.toSimple(x.name),
            time: s.time(x.updateTime),
          })),
        windows: nearestNowcast(p.nowcast.data, r.lat, r.lon).map((x) => ({
          time: s.time(x.end),
          value: s.value(x.value),
        })),
        forecast: (p.forecast.data.weatherForecast || []).map((f) => ({
          date: f.forecastDate,
          week: s.toSimple(f.week),
          description: s.toSimple(f.forecastWeather),
          min: s.value(f.forecastMintemp && f.forecastMintemp.value),
          max: s.value(f.forecastMaxtemp && f.forecastMaxtemp.value),
        })),
        synopsis: s.toSimple(
          p.local.data.forecastDesc || p.forecast.data.generalSituation,
        ),
        sources: Object.keys(p)
          .filter((k) =>
            [
              "rain",
              "weather",
              "warnings",
              "forecast",
              "local",
              "nowcast",
              "tides",
            ].includes(k),
          )
          .map((k) => s.status(k, p[k])),
        historical: Object.values(p).some((x) => x.origin === "snapshot"),
      });
    } catch (e) {
      s.toast(e);
    } finally {
      this.setData({ loading: false });
    }
  },
  regionChange(e) {
    const c = { ...s.config(), region: s.regions[+e.detail.value].name };
    getApp().saveConfig(c);
    this.refresh();
  },
  settings() {
    wx.navigateTo({ url: "/pages/settings/index" });
  },
  knowledge() {
    wx.navigateTo({ url: "/pages/knowledge/index" });
  },
  source(e) {
    s.copy(e.currentTarget.dataset.url);
  },
});
