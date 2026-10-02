import { createRouter, createWebHistory } from "vue-router";
import { publicBase } from "../utils/public-base";
import AppLayout from "../layouts/AppLayout.vue";
import DashboardView from "../views/DashboardView.vue";
import PredictionView from "../views/PredictionView.vue";
import OrdersView from "../views/OrdersView.vue";
import StallsView from "../views/StallsView.vue";
import OffersView from "../views/OffersView.vue";
import FeedbackView from "../views/FeedbackView.vue";
import AlertsView from "../views/AlertsView.vue";
import ReportsView from "../views/ReportsView.vue";
import InsightsView from "../views/InsightsView.vue";
import AboutView from "../views/AboutView.vue";
import LoginView from "../views/LoginView.vue";

const routes = [
  { path: "/login", component: LoginView },
  {
    path: "/app",
    component: AppLayout,
    children: [
      { path: "", redirect: "/app/dashboard" },
      { path: "dashboard", component: DashboardView, meta: { title: "经营驾驶舱", active: "dashboard" } },
      { path: "prediction", component: PredictionView, meta: { title: "备餐决策中心", active: "prediction" } },
      { path: "orders", component: OrdersView, meta: { title: "订单核销", active: "orders" } },
      { path: "stalls", component: StallsView, meta: { title: "档口与菜品", active: "stalls" } },
      { path: "reports", component: ReportsView, meta: { title: "经营复盘报告", active: "reports" } },
      { path: "offers", component: OffersView, meta: { title: "限时优惠", active: "offers" } },
      { path: "operation-feedback", redirect: "/app/operations/feedback" },
      { path: "operations/feedback", component: FeedbackView, meta: { title: "经营数据回传", active: "operation-feedback" } },
      { path: "alerts", component: AlertsView, meta: { title: "经营预警中心", active: "alerts" } },
      { path: "insights/realtime", component: InsightsView, meta: { title: "实时经营分析", active: "insights-realtime", insight: "realtime" } },
      { path: "insights/demand", component: InsightsView, meta: { title: "需求预测分析", active: "insights-demand", insight: "demand" } },
      { path: "insights/waste", component: InsightsView, meta: { title: "减损场景分析", active: "insights-waste", insight: "waste" } },
      { path: "about", component: AboutView, meta: { title: "服务说明", active: "about" } },
      { path: ":pathMatch(.*)*", redirect: "/app/dashboard" },
    ],
  },
];

export default createRouter({
  history: createWebHistory(publicBase),
  routes,
  scrollBehavior: () => ({ top: 0 }),
});
