package org.foodwise.prediction;

import java.time.LocalDate;

/** Missing dates remain absent observations rather than being fabricated as zero sales. */
public record SalesObservation(LocalDate date, int sold, int prepared) {}
