package com.garageeducation.harness;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Starts the harness.
 *
 * <p>Spring Boot scans this package and creates every bean in it.
 * The OpenAI starter adds a {@code ChatClient.Builder} for LM Studio.
 *
 * <p>The {@code main} method is package-private and {@code static}.
 * Java 25 and later accept this form.
 */
@SpringBootApplication
public class HarnessApplication {

	/**
	 * Runs the Spring Boot application on port 8080.
	 *
	 * @param args command-line arguments, passed to Spring Boot
	 */
	static void main(String[] args) {
		SpringApplication.run(HarnessApplication.class, args);
	}

}
