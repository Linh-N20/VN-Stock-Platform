package com.stockplatform.controller;

import java.util.List;
import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.stereotype.Controller;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseBody;

import com.stockplatform.entity.FavoriteStock;
import com.stockplatform.repository.FavoriteStockRepository;
import com.stockplatform.security.CustomOAuth2User;

@Controller
@RequestMapping("/api/favorites")
public class FavoriteController {

    private final FavoriteStockRepository favoriteRepo;

    public FavoriteController(FavoriteStockRepository favoriteRepo) {
        this.favoriteRepo = favoriteRepo;
    }

    @GetMapping
    @ResponseBody
    public ResponseEntity<?> getFavorites(Authentication auth) {
        if (auth == null || !(auth.getPrincipal() instanceof CustomOAuth2User user)) {
            return ResponseEntity.status(401).body(Map.of("error", "Chưa đăng nhập"));
        }
        List<String> symbols = favoriteRepo
            .findByUserEmailOrderByAddedAtDesc(user.getEmail())
            .stream().map(FavoriteStock::getSymbol).toList();
        return ResponseEntity.ok(Map.of("favorites", symbols));
    }

    @GetMapping("/check/{symbol}")
    @ResponseBody
    public ResponseEntity<?> check(@PathVariable String symbol, Authentication auth) {
        if (auth == null || !(auth.getPrincipal() instanceof CustomOAuth2User user)) {
            return ResponseEntity.ok(Map.of("favorited", false));
        }
        boolean isFav = favoriteRepo.existsByUserEmailAndSymbol(
            user.getEmail(), symbol.toUpperCase().trim());
        return ResponseEntity.ok(Map.of("favorited", isFav));
    }

    @PostMapping("/toggle/{symbol}")
    @ResponseBody
    @Transactional
    public ResponseEntity<?> toggle(@PathVariable String symbol, Authentication auth) {
        if (auth == null || !(auth.getPrincipal() instanceof CustomOAuth2User user)) {
            return ResponseEntity.status(401).body(Map.of("error", "Chưa đăng nhập"));
        }
        String email  = user.getEmail();
        String sym    = symbol.toUpperCase().trim();
        boolean isFav = favoriteRepo.existsByUserEmailAndSymbol(email, sym);

        if (isFav) {
            favoriteRepo.deleteByUserEmailAndSymbol(email, sym);
        } else {
            favoriteRepo.save(new FavoriteStock(email, sym));
        }

        return ResponseEntity.ok(Map.of(
            "symbol",    sym,
            "favorited", !isFav,
            "message",   !isFav ? "Đã thêm vào yêu thích" : "Đã xóa khỏi yêu thích"
        ));
    }
}