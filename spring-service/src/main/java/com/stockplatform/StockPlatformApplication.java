package com.stockplatform;

import io.github.cdimascio.dotenv.Dotenv;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class StockPlatformApplication {

    public static void main(String[] args) {
        // Load file .env vào System properties trước khi Spring Boot khởi động
        // ignoreIfMissing() → không crash nếu chạy trên server không có file .env
        Dotenv dotenv = Dotenv.configure()
            .ignoreIfMissing()
            .load();

        dotenv.entries().forEach(entry ->
            System.setProperty(entry.getKey(), entry.getValue())
        );

        SpringApplication.run(StockPlatformApplication.class, args);
    }
}