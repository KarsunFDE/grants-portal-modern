package com.karsunfde.grantsportal.gateway;

import org.springframework.cloud.gateway.route.RouteLocator;
import org.springframework.cloud.gateway.route.builder.RouteLocatorBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Gateway route definitions.
 *
 * Routes:
 *   /api/grant-applications/**   → grant-application-service:8081
 *   /api/peer-reviews/**     → peer-review-service:8082
 *   /api/ai/**              → ai-orchestrator:8000
 *   /api/public/**          → grant-application-service (signature-skipped path — Item 1)
 */
@Configuration
public class RouteConfig {

    @Bean
    public RouteLocator routes(RouteLocatorBuilder builder) {
        String grantApplicationUrl = System.getenv().getOrDefault(
            "SOLICITATION_SERVICE_URL", "http://grant-application-service:8081");
        String peerReviewUrl = System.getenv().getOrDefault(
            "EVALUATION_SERVICE_URL", "http://peer-review-service:8082");
        String aiUrl = System.getenv().getOrDefault(
            "AI_ORCHESTRATOR_URL", "http://ai-orchestrator:8000");

        return builder.routes()
            .route("grantApplications", r -> r.path("/api/grant-applications/**").uri(grantApplicationUrl))
            .route("peerReviews",   r -> r.path("/api/peer-reviews/**").uri(peerReviewUrl))
            .route("ai",            r -> r.path("/api/ai/**").uri(aiUrl))
            // Item 1 — public path forwards to grant-application-service after signature-skip.
            .route("public",        r -> r.path("/api/public/**").uri(grantApplicationUrl))
            .build();
    }
}
