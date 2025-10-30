import time

from intelligence.joke_cache import JokeCache


def test_rotation_of_responses():
    jc = JokeCache(ttl_seconds=10, max_size=10)
    prompt = "Une blague courte sur les robots"
    # Seed multiple distinct responses
    jc.set(prompt, "Blague A")
    jc.set(prompt, "Blague B")
    jc.set(prompt, "Blague C")

    # Should rotate through A, B, C, A
    r1 = jc.get(prompt)
    r2 = jc.get(prompt)
    r3 = jc.get(prompt)
    r4 = jc.get(prompt)

    assert r1 in {"Blague A", "Blague B", "Blague C"}
    assert r2 in {"Blague A", "Blague B", "Blague C"}
    assert r3 in {"Blague A", "Blague B", "Blague C"}
    assert r4 in {"Blague A", "Blague B", "Blague C"}

    # Ensure not all equal (very unlikely); specifically check rotation pattern length
    assert len({r1, r2, r3}) >= 2


def test_try_acquire_release():
    jc = JokeCache()
    prompt = "Prompt concurrent"

    assert jc.try_acquire(prompt) is True
    # second acquire should fail
    assert jc.try_acquire(prompt) is False

    jc.release(prompt)
    # after release, acquire should succeed again
    assert jc.try_acquire(prompt) is True
    jc.release(prompt)
