App({
  globalData: { packets: {}, sharedToken: "", drafts: [] },
  onLaunch() {
    this.globalData.config = wx.getStorageSync("rg-config") || {
      baseUrl: "http://127.0.0.1:8095",
      region: "沙田",
      mode: "live",
      actor: "",
    };
  },
  saveConfig(config) {
    this.globalData.config = config;
    wx.setStorageSync("rg-config", config);
  },
});
