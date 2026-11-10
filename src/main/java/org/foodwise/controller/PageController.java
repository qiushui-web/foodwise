package org.foodwise.controller;

import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;

@Controller
public class PageController {

    @GetMapping({"/app", "/app/", "/app/{*path}"})
    public String vueApp(@PathVariable(required = false) String path, HttpServletResponse response) {
        // 未知前端路径仍返回单页外壳（由前端渲染“页面未找到”），但状态码必须诚实。
        if (!SpaRoutes.isKnown(path)) {
            response.setStatus(HttpServletResponse.SC_NOT_FOUND);
        }
        return "app";
    }

    @GetMapping({"/", "/dashboard"})
    public String dashboard() { return "redirect:/app/dashboard"; }

    @GetMapping("/login")
    public String login(Model model) {
        model.addAttribute("pageTitle", "运营登录");
        return "login";
    }

    /**
     * Demo mode has no Spring Security login filter. Keep the same form usable
     * locally; when security is enabled, the filter handles this path first.
     */
    @PostMapping("/login")
    public String demoLogin() {
        return "redirect:/app/dashboard";
    }

    @GetMapping("/stalls")
    public String stalls() { return "redirect:/app/stalls"; }

    @GetMapping("/prediction")
    public String prediction() { return "redirect:/app/prediction"; }

    @GetMapping("/offers")
    public String offers() { return "redirect:/app/offers"; }

    @GetMapping("/orders")
    public String orders() { return "redirect:/app/orders"; }

    @GetMapping("/operations/feedback")
    public String operationFeedback() { return "redirect:/app/operations/feedback"; }

    @GetMapping("/reports")
    public String reports() { return "redirect:/app/reports"; }

    @GetMapping("/alerts")
    public String alerts() { return "redirect:/app/alerts"; }

    @GetMapping("/insights/realtime")
    public String realtimeInsights() { return "redirect:/app/insights/realtime"; }

    @GetMapping("/insights/demand")
    public String demandInsights() { return "redirect:/app/insights/demand"; }

    @GetMapping("/insights/waste")
    public String wasteInsights() { return "redirect:/app/insights/waste"; }

    @GetMapping("/about")
    public String about() { return "redirect:/app/about"; }
}

