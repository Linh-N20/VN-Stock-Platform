package com.stockplatform.controller;

import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;

@Controller
@RequestMapping("/learn")
public class LearnController {

    @GetMapping
    public String learnHome(Model model) {
        return "learn/index";
    }

    @GetMapping("/{topic}")
    public String learnTopic(@PathVariable String topic, Model model) {
        model.addAttribute("topic", topic);
        return "learn/" + topic;
    }
}
