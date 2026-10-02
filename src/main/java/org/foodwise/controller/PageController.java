package org.foodwise.controller;

import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;

@Controller
public class PageController {

    @GetMapping({"/app", "/app/", "/app/{*path}"})
    public String vueApp() {
        return "app";
    }

    @GetMapping({"/", "/dashboard"})
    public String dashboard() { return "redirect:/app/dashboard"; }

    @GetMapping("/login")
    public String login(Model model) {
        model.addAttribute("pageTitle", "运营登录");
        return "login";
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

