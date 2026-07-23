package com.stockplatform.repository;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import com.stockplatform.entity.StockSignal;

public interface StockSignalRepository extends JpaRepository<StockSignal, Long> {

    Optional<StockSignal> findTopBySymbolOrderByCalculatedAtDesc(String symbol);

    // Lấy tín hiệu mới nhất của từng symbol trong danh sách
    @Query("""
        SELECT s FROM StockSignal s
        WHERE s.symbol IN :symbols
        AND s.calculatedAt = (
            SELECT MAX(s2.calculatedAt)
            FROM StockSignal s2
            WHERE s2.symbol = s.symbol
        )
        ORDER BY s.calculatedAt DESC
    """)
    List<StockSignal> findBySymbolInOrderByCalculatedAtDesc(@Param("symbols") List<String> symbols);
}