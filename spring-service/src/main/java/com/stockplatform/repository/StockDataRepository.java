package com.stockplatform.repository;

import com.stockplatform.entity.StockData;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

public interface StockDataRepository extends JpaRepository<StockData, Long> {

    List<StockData> findBySymbolOrderByDateAsc(String symbol);

    @Query("SELECT s FROM StockData s WHERE s.symbol = :symbol AND s.date >= :from ORDER BY s.date ASC")
    List<StockData> findBySymbolAndDateAfter(@Param("symbol") String symbol,
                                              @Param("from") LocalDate from);

    Optional<StockData> findTopBySymbolOrderByDateDesc(String symbol);

    boolean existsBySymbolAndDate(String symbol, LocalDate date);
}
