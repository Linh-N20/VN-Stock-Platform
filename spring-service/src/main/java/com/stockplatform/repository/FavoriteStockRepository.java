package com.stockplatform.repository;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

import com.stockplatform.entity.FavoriteStock;

public interface FavoriteStockRepository extends JpaRepository<FavoriteStock, Long> {

    Optional<FavoriteStock> findByUserEmailAndSymbol(String userEmail, String symbol);

    List<FavoriteStock> findByUserEmailOrderByAddedAtDesc(String userEmail);

    boolean existsByUserEmailAndSymbol(String userEmail, String symbol);

    void deleteByUserEmailAndSymbol(String userEmail, String symbol);
}