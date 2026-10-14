const s = require("../../utils/service");
Page({
  data: { kind: "rain", query: "", rows: [], loading: false, source: null },
  onShow() {
    this.refresh();
  },
  onPullDownRefresh() {
    this.refresh().finally(() => wx.stopPullDownRefresh());
  },
  async refresh() {
    this.setData({ loading: true });
    try {
      await s.load(["rain", "weather", "tides"]);
      this.render();
    } catch (e) {
      s.toast(e);
    } finally {
      this.setData({ loading: false });
    }
  },
  category(e) {
    this.setData({ kind: e.currentTarget.dataset.kind });
    this.render();
  },
  search(e) {
    this.setData({ query: e.detail.value });
    this.render();
  },
  render() {
    const p = getApp().globalData.packets[this.data.kind],
      d = p.data;
    let rows =
      this.data.kind === "rain"
        ? d.hourlyRainfall.map((r) => ({
            id: r.automaticWeatherStationID,
            name: s.toSimple(r.automaticWeatherStation),
            value: s.value(r.value),
            unit: "mm",
            time: s.time(d.obsTime),
          }))
        : this.data.kind === "weather"
          ? d.rainfall.data.map((r) => ({
              id: r.place,
              name: s.toSimple(r.place),
              value: s.value(r.max),
              unit: "mm 上限",
              time: s.time(d.rainfall.endTime),
            }))
          : d.map((r) => ({
              id: r.name,
              name: r.name,
              value: s.value(r.value),
              unit: "mCD",
              time: s.time(r.time),
            }));
    this.setData({
      rows: rows.filter((r) =>
        r.name
          .toLowerCase()
          .includes(s.toSimple(this.data.query).toLowerCase()),
      ),
      source: s.status(this.data.kind, p),
    });
  },
  copy() {
    s.copy(this.data.source.source);
  },
});
