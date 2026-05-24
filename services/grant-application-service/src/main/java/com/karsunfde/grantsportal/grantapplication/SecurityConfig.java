package com.karsunfde.grantsportal.grantapplication;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configuration.WebSecurityConfigurerAdapter;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.util.List;

/**
 * Dev-default security: assume requests passed through the api-gateway and
 * trust them. Downstream services do not re-validate the JWT — which is part
 * of why Item 1 (gateway signature-skip) is so dangerous.
 *
 * For W1 day-1 smoke-test purposes, we permit all so the cohort can curl
 * endpoints directly during the brownfield-debt walkthrough. Real prod config
 * would re-validate.
 *
 * Era-authentic Karsun-legacy pattern: {@link WebSecurityConfigurerAdapter}
 * + {@code configure(HttpSecurity)} + {@code authorizeRequests().antMatchers()}.
 * Deprecated in Spring Security 5.7 (in favor of the {@code SecurityFilterChain}
 * bean style), but it remains the dominant pattern across real Karsun federal
 * estates on Boot 2.3–2.5 / Security 5.4 era. Cohort migrates this to the
 * modern bean DSL during the W4–W5 modernization arc.
 *
 * ⚠ DELIBERATE — Pair-unique debt sec-cors-wildcard-credentials (D-059):
 *   The {@code corsConfig()} bean below configures the CORS layer with a
 *   wildcard origin pattern AND credentials = true. This is an explicit
 *   spec violation — browsers will reject the combo, but the
 *   server-side config still advertises it. Cross-origin attacker on
 *   evil.example can issue authenticated reads against
 *   /api/grant-applications by sniffing the response headers.
 *   Cohort fix lands W4 Wed (AI Security Engineering Day, OWASP API01).
 */
@Configuration
@EnableWebSecurity
public class SecurityConfig extends WebSecurityConfigurerAdapter {

    @Override
    protected void configure(HttpSecurity http) throws Exception {
        http
            .cors().and()
            .csrf().disable()
            .authorizeRequests()
                .anyRequest().permitAll();
    }

    /**
     * ⚠ DELIBERATE — Pair-unique debt: sec-cors-wildcard-credentials.
     *
     * Wildcard origin + allowCredentials=true. Either flag alone would be
     * defensible (wildcard for fully-public read endpoints, credentials for
     * a locked-down origin list). The combination is an OWASP API01 finding.
     * Cohort discovers via OPTIONS preflight test in W4.
     */
    @Bean
    public CorsConfigurationSource corsConfig() {
        CorsConfiguration c = new CorsConfiguration();
        c.addAllowedOriginPattern("*");
        c.setAllowCredentials(true);
        c.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE", "OPTIONS"));
        c.setAllowedHeaders(List.of("*"));

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", c);
        return source;
    }
}
