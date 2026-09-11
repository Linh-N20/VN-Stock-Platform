package com.stockplatform.repository;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import com.stockplatform.entity.WatchedStock;

public interface WatchedStockRepository extends JpaRepository<WatchedStock, Long> {

    Optional<WatchedStock> findBySymbol(String symbol);

    /**
     * Lấy watchlist theo thứ tự:
     * cổ phiếu được xem gần nhất → cổ phiếu cũ nhất.
     */
    @Query("""
        SELECT w
        FROM WatchedStock w
        ORDER BY w.lastViewedAt DESC
    """)
    List<WatchedStock> findRecentlyWatched();
}