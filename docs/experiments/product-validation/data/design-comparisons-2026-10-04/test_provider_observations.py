from provider_observations import admission_delay, rate_headers, reset_seconds


def test_only_numeric_rate_headers_are_kept():
    assert rate_headers(
        {
            "authorization": "secret",
            "retry-after": "12",
            "x-ratelimit-limit-tokens": "private-secret",
        }
    ) == {"retry-after": "12"}


def test_compound_reset_and_elapsed_are_respected():
    assert reset_seconds("1m2.5s") == 62.5
    assert reset_seconds("malformed") == 0
    headers = {
        "x-ratelimit-remaining-tokens": "1",
        "x-ratelimit-reset-tokens": "1m2.5s",
    }
    assert admission_delay(headers, 10, 2000) == 53.5


def test_enough_capacity_does_not_wait_a_whole_bucket():
    assert admission_delay({"x-ratelimit-remaining-tokens": "100000"}, 8, 2000) == 0


def test_large_input_is_paced_even_if_previous_remaining_was_full():
    assert (
        admission_delay(
            {
                "x-ratelimit-remaining-tokens": "200000",
                "x-ratelimit-limit-tokens": "200000",
            },
            0,
            80_000,
        )
        == 30.27456
    )
