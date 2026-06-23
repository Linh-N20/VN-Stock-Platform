package com.stockplatform.repository;

import com.stockplatform.entity.StockSignal;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.Optional;

public interface StockSignalRepository extends JpaRepository<StockSignal, Long> {

    Optional<StockSignal> findTopBySymbolOrderByCalculatedAtDesc(String symbol);

    List<StockSignal> findTop10BySymbolOrderByCalculatedAtDesc(String symbol);

    List<StockSignal> findTopBySignalOrderByCalculatedAtDesc(String signal);
}
