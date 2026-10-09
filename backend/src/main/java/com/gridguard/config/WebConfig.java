package com.gridguard.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Web Configuration for serving static frontend and CORS
 */
@Configuration
public class WebConfig implements WebMvcConfigurer {

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOrigins("*", "http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173",
                        "http://localhost:8080")
                .allowedMethods("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS")
                .allowedHeaders("*")
                .allowCredentials(true)
                .maxAge(3600);
    }

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        // Serve static frontend resources
        registry.addResourceHandler("/static/**")
                .addResourceLocations("classpath:/static/");

        // Serve index.html for root path
        registry.addResourceHandler("/")
                .addResourceLocations("classpath:/static/")
                .resourceChain(true)
                .addResolver(new org.springframework.web.servlet.resource.PathResourceResolver() {
                    @Override
                    protected org.springframework.core.io.Resource getResource(String resourcePath,
                            org.springframework.core.io.Resource location) {
                        try {
                            org.springframework.core.io.Resource requestedResource = location
                                    .createRelative(resourcePath);
                            return requestedResource.exists() && requestedResource.isReadable() ? requestedResource
                                    : new org.springframework.core.io.ClassPathResource("/static/index.html");
                        } catch (java.io.IOException exception) {
                            return new org.springframework.core.io.ClassPathResource("/static/index.html");
                        }
                    }
                });
    }
}