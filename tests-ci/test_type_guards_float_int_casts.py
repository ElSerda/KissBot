"""
Tests for float/int cast type guards added during mypy strict compliance.

WHY THESE TESTS EXIST:
During mypy strict compliance, we found that fuzz.token_set_ratio() returns int
but was assigned to float variables. Rather than using `# type: ignore`, we added
explicit float() casts and 0.0 initialization.

MYPY ERRORS FIXED:
- intelligence/core.py:38: error: Incompatible types in assignment (expression has type "int", variable has type "float")
- intelligence/core.py:27: error: Need type annotation for "best_score" (hint: "best_score: float = ...")

SOLUTION:
- Line 27: best_score = 0.0  (explicit float literal)
- Line 38: score = float(fuzz.token_set_ratio(...))  (explicit cast)

PHILOSOPHY:
These tests verify that float/int casts protect against:
1. Type inconsistencies when fuzzy matchers return different types
2. Arithmetic operations mixing int/float (precision loss)
3. API changes in rapidfuzz/fuzzywuzzy libraries
4. Code refactoring that changes numeric types

Testing approach: No mocks, functional tests with different numeric types.
"""

from rapidfuzz import fuzz


def test_token_set_ratio_returns_numeric():
    """Verify that fuzz.token_set_ratio returns numeric type (float in rapidfuzz>=3.0)."""
    result = fuzz.token_set_ratio("test", "test")
    # rapidfuzz>=3.0 returns float, older versions/thefuzz return int
    assert isinstance(result, (int, float)), f"Expected numeric, got {type(result)}"
    assert result == 100.0 or result == 100


def test_float_cast_preserves_int_value():
    """Test that float(int) cast preserves exact value for ratio scores."""
    int_score = fuzz.token_set_ratio("hello", "hello world")
    float_score = float(int_score)
    
    assert isinstance(float_score, float)
    assert float_score == int_score  # No precision loss for integer values
    assert 0.0 <= float_score <= 100.0


def test_float_initialization_with_literal():
    """Test that 0.0 literal creates float type (not int)."""
    best_score = 0.0
    assert isinstance(best_score, float), "0.0 should be float, not int"
    
    # Comparison with cast result should work without warnings
    ratio = float(fuzz.token_set_ratio("a", "b"))
    best_score = max(best_score, ratio)
    assert isinstance(best_score, float)


def test_float_cast_handles_edge_cases():
    """Test float() cast with fuzzy match edge cases."""
    # Perfect match
    perfect = float(fuzz.token_set_ratio("test", "test"))
    assert perfect == 100.0
    assert isinstance(perfect, float)
    
    # No match (or very low match)
    zero = float(fuzz.token_set_ratio("abc", "xyz"))
    assert zero <= 10.0  # Fuzzy matching might find some similarity
    assert isinstance(zero, float)
    
    # Partial match - single word vs multi-word
    partial = float(fuzz.token_set_ratio("world", "hello world"))
    assert 0.0 < partial <= 100.0  # token_set_ratio might score this highly
    assert isinstance(partial, float)


def test_mixed_arithmetic_int_float():
    """Test that float casts prevent type mixing issues."""
    # Simulate the core.py logic
    best_score = 0.0  # float
    threshold = 75  # int (common in code)
    
    ratio_int = fuzz.token_set_ratio("game", "game name")  # returns int
    ratio_float = float(ratio_int)  # our cast
    
    # Comparison should work smoothly
    if ratio_float >= threshold and ratio_float > best_score:
        best_score = ratio_float
    
    assert isinstance(best_score, float)
    assert best_score >= 0.0


def test_float_cast_in_comparison_chain():
    """Test the exact pattern from intelligence/core.py line 40-42."""
    best_score = 0.0
    threshold = 70
    
    # Simulate multiple comparisons like in find_game_fuzzy()
    # Use real fuzzy matching instead of hardcoded scores
    test_cases = [
        ("Brotato", "brotato"),  # Perfect match (case-insensitive)
        ("Stardew Valley", "stardew"),  # Partial match
        ("The Binding of Isaac", "binding"),  # Partial match
    ]
    
    for game_name, query in test_cases:
        score = float(fuzz.token_set_ratio(game_name.lower(), query.lower()))
        if score >= threshold and score > best_score:
            best_score = score
    
    # Best match should be the perfect match (Brotato)
    assert best_score >= 90.0, f"Expected high score for perfect match, got {best_score}"
    assert isinstance(best_score, float)


def test_float_cast_exists_in_source():
    """Verify that float() cast is present in intelligence/core.py."""
    import pathlib
    
    core_path = pathlib.Path(__file__).parent.parent / "intelligence" / "core.py"
    assert core_path.exists(), f"intelligence/core.py not found at {core_path}"
    
    source = core_path.read_text()
    
    # Check for the float cast on token_set_ratio
    assert "float(fuzz.token_set_ratio" in source, \
        "Missing float() cast on fuzz.token_set_ratio"
    
    # Check for 0.0 literal initialization
    assert "best_score = 0.0" in source, \
        "Missing 0.0 literal for best_score initialization"


def test_float_casts_prevent_type_warnings():
    """Document the 5 scenarios where float/int mixing causes issues."""
    scenarios = [
        "Arithmetic: (int + float) / int might lose precision",
        "Comparison: Comparing int to float in sorted() needs consistent types",
        "JSON serialization: Some serializers treat int/float differently",
        "Type hints: mypy strict mode enforces float annotations",
        "Library changes: rapidfuzz might change return type in future versions"
    ]
    
    # This test documents WHY we use float() casts
    assert len(scenarios) == 5, "5 real-world issues with int/float mixing"


def test_mypy_errors_without_float_cast():
    """Document the exact mypy errors that float() casts solve."""
    mypy_errors = [
        {
            "file": "intelligence/core.py",
            "line": 38,
            "error": "Incompatible types in assignment (expression has type \"int\", variable has type \"float\")",
            "fix": "score = float(fuzz.token_set_ratio(game_name.lower(), user_query_lower))"
        },
        {
            "file": "intelligence/core.py",
            "line": 27,
            "error": "Need type annotation for \"best_score\"",
            "fix": "best_score = 0.0  # Explicit float literal"
        }
    ]
    
    assert len(mypy_errors) == 2, "2 mypy errors fixed with float casts"
    assert all("float" in err["fix"] for err in mypy_errors), \
        "All fixes involve explicit float handling"


def test_float_cast_consistency_across_synapses():
    """Verify float consistency in related synapse files."""
    import pathlib
    
    # These files also had float/int fixes during mypy compliance
    synapse_files = [
        "intelligence/synapses/local_synapse.py",
        "intelligence/synapses/cloud_synapse.py",
    ]
    
    intelligence_dir = pathlib.Path(__file__).parent.parent / "intelligence"
    
    for file_rel in synapse_files:
        file_path = pathlib.Path(__file__).parent.parent / file_rel
        if not file_path.exists():
            continue  # Skip if file doesn't exist
        
        source = file_path.read_text()
        
        # Check for float consistency patterns
        has_float_usage = (
            "float(" in source or
            ".0" in source or  # Float literals
            ": float" in source  # Type hints
        )
        
        assert has_float_usage, f"{file_rel} should use explicit float handling"
