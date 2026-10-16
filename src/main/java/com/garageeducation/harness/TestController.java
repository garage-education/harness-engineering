package com.garageeducation.harness;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * Exposes {@link Assistant} over HTTP for manual tests.
 *
 * <p>Example: {@code GET http://localhost:8080/?input=how many error events in checkout service?}
 */
@RestController
public class TestController {

    private final Assistant assistant;

    /**
     * Creates the controller.
     *
     * @param assistant the assistant that answers each request
     */
    public TestController(Assistant assistant) {
        this.assistant = assistant;
    }

    /**
     * Sends the {@code input} query parameter to the model.
     *
     * @param input the question; the request fails without it
     * @return the model's text reply
     */
    @GetMapping("/")
    public String test(@RequestParam String input) {
        return assistant.ask(input);
    }
}
