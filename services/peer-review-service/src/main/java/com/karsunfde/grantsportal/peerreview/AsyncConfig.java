package com.karsunfde.grantsportal.peerreview;

import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;

/** Enables {@code @Async} so audit writes run on a separate thread (Item 2 mirror). */
@Configuration
@EnableAsync
public class AsyncConfig {
}
