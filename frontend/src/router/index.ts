import { createRouter, createWebHistory } from "vue-router";
import { publicBase } from "../utils/public-base";
import AppLayout from "../layouts/AppLayout.vue";
const DashboardView = () => import("../views/DashboardView.vue");
const PredictionView = () => import("../views/PredictionView.vue");
const OrdersView = () => import("../views/OrdersView.vue");
const StallsView = () => import("../views/StallsView.vue");
const OffersView = () => import("../views/OffersView.vue");
const FeedbackView = () => import("../views/FeedbackView.vue");
const AlertsView = () => import("../views/AlertsView.vue");
const ReportsView = () => import("../views/ReportsView.vue");
const InsightsView = () => import("../views/InsightsView.vue");
const AboutView = () => import("../views/AboutView.vue");
const NotFoundView = () => import("../views/NotFoundView.vue");
const LoginView = () => import("../views/LoginView.vue");
const OnboardingView = () => import("../views/OnboardingView.vue");
const EvidenceView = () => import("../views/EvidenceView.vue");

const routes = [
  { path: "/login", component: LoginView, meta: { title: "运营登录" } },
  {
    path: "/app",
    component: AppLayout,
    children: [
      { path: "", redirect: "/app/dashboard" },
      { path: "dashboard", component: DashboardView, meta: { title: "经营总览", active: "dashboard" } },
      { path: "prediction", component: PredictionView, meta: { title: "备餐计划", active: "prediction" } },
      { path: "orders", component: OrdersView, meta: { title: "订单核销", active: "orders" } },
      { path: "stalls", component: StallsView, meta: { title: "档口与菜品", active: "stalls" } },
      { path: "onboarding", component: OnboardingView, meta: { title: "首次建档", active: "onboarding" } },
      { path: "reports", component: ReportsView, meta: { title: "经营复盘报告", active: "reports" } },
      { path: "offers", component: OffersView, meta: { title: "限时优惠", active: "offers" } },
      { path: "operation-feedback", redirect: "/app/operations/feedback" },
      { path: "operations/feedback", component: FeedbackView, meta: { title: "记录当天经营", active: "operation-feedback" } },
      { path: "alerts", component: AlertsView, meta: { title: "经营预警中心", active: "alerts" } },
      { path: "insights/realtime", component: InsightsView, meta: { title: "营业快照分析", active: "insights-realtime", insight: "realtime" } },
      { path: "insights/demand", component: InsightsView, meta: { title: "需求预测分析", active: "insights-demand", insight: "demand" } },
      { path: "insights/waste", component: InsightsView, meta: { title: "减损场景分析", active: "insights-waste", insight: "waste" } },
      { path: "about", component: AboutView, meta: { title: "服务说明", active: "about" } },
      { path: "evidence", component: EvidenceView, meta: { title: "数据说明", active: "evidence" } },
      { path: ":pathMatch(.*)*", component: NotFoundView, meta: { title: "页面未找到", active: "dashboard" } },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(publicBase),
  routes,
  scrollBehavior: () => ({ top: 0 }),
});

router.afterEach((to) => {
  const brand = "食刻有数";
  const pageTitle = String(to.meta.title || brand);
  document.title = pageTitle.includes(brand) ? pageTitle : `${pageTitle} | ${brand}`;
});
export default router;
