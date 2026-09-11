package com.stockplatform.repository;

import com.stockplatform.entity.PredictionRecord;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

public interface PredictionRepository extends JpaRepository<PredictionRecord, Long> {

    Optional<PredictionRecord> findBySymbolAndForDate(String symbol, LocalDate forDate);

    List<PredictionRecord> findBySymbolOrderByForDateDesc(String symbol);

    // Lấy 10 dự đoán gần nhất của 1 mã
    List<PredictionRecord> findTop10BySymbolOrderByForDateDesc(String symbol);

    // Lấy tất cả dự đoán chưa được đối chiếu (chưa có kết quả thực tế)
    List<PredictionRecord> findByActualDirectionIsNullAndForDateBefore(LocalDate date);

    // Thống kê accuracy theo symbol
    @Query("""
        SELECT COUNT(p) as total,
               SUM(CASE WHEN p.isCorrect = true THEN 1 ELSE 0 END) as correct
        FROM PredictionRecord p
        WHERE p.symbol = :symbol AND p.isCorrect IS NOT NULL
    """)
    Object[] getAccuracyStats(@Param("symbol") String symbol);

    // Accuracy tổng thể
    @Query("""
        SELECT COUNT(p) as total,
               SUM(CASE WHEN p.isCorrect = true THEN 1 ELSE 0 END) as correct
        FROM PredictionRecord p
        WHERE p.isCorrect IS NOT NULL
    """)
    Object[] getOverallAccuracyStats();
}
