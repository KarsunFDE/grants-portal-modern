package com.karsunfde.grantsportal.peerreview.client;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import java.util.Map;

/**
 * ⚠ DELIBERATE BROWNFIELD DEBT — Item 3 ⚠
 *
 * Calls grant-application-service over synchronous REST. No:
 *   - {@code @CircuitBreaker} (Resilience4j not on the classpath)
 *   - {@code @TimeLimiter}
 *   - {@code @Retry}
 *   - fallback method
 *   - timeout on the RestTemplate
 *   - idempotency key on state-mutating calls
 *
 * A slow upstream piles threads on this service's Tomcat connector. A load
 * test from peer-review-service → grant-application-service (artificially slow)
 * will reproduce thread exhaustion.
 *
 * Cohort fixes in W4 Thu reliability engineering.
 */
@Component
public class GrantApplicationClient {

    private static final Logger log = LoggerFactory.getLogger(GrantApplicationClient.class);

    private final RestTemplate restTemplate;

    @Value("${grantApplication.service.url:http://grant-application-service:8081}")
    private String grantApplicationServiceUrl;

    @Autowired
    public GrantApplicationClient(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    /**
     * Fetch a grantApplication by id from the upstream service.
     *
     * ⚠ No try/catch — a 5xx from upstream propagates as a 500 from us.
     * ⚠ No timeout — a 30-second hang upstream is a 30-second hang here.
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> getGrantApplication(String id) {
        String url = grantApplicationServiceUrl + "/api/grant-applications/" + id;
        // Item 6 — peer-review-service uses traceId key.
        log.info("calling grant-application-service url={} traceId=N/A", url);
        return restTemplate.getForObject(url, Map.class);
    }
}
