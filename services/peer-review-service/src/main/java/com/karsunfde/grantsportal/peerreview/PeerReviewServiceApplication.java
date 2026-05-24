package com.karsunfde.grantsportal.peerreview;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.web.client.RestTemplate;

/**
 * acquire-gov — PeerReview Service.
 *
 * Coordinates peer_review panels for grant_applications. Calls grant-application-service
 * synchronously to fetch grant_application data (⚠ no circuit breaker — Item 3).
 *
 * Brownfield-debt items in this service:
 *   - Item 3 — No Resilience4j circuit breaker on outbound calls
 *   - Item 6 — Logs traceId (inconsistent with X-Request-ID / correlationId)
 *   - Item 11 — Dockerfile uses :latest
 */
@SpringBootApplication
public class PeerReviewServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(PeerReviewServiceApplication.class, args);
    }

    /**
     * ⚠ DELIBERATE — Item 3: no timeout configuration, no error handler, no
     * circuit breaker wrapper. A slow grant-application-service will pile threads
     * on this RestTemplate.
     */
    @Bean
    public RestTemplate restTemplate() {
        return new RestTemplate();
    }
}
