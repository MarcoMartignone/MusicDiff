#!/usr/bin/env python3
"""Test script for matcher.py - Track matching algorithm"""

from musicdiff.matcher import TrackMatcher

def test_isrc_matching():
    """Test ISRC-based matching (100% reliable)."""
    print("Testing: ISRC matching...")

    matcher = TrackMatcher()

    source = {
        'title': 'Get Lucky',
        'artist': 'Daft Punk',
        'album': 'Random Access Memories',
        'duration_ms': 248000,
        'isrc': 'USCOLUMN123456'
    }

    candidates = [
        {
            'title': 'Get Lucky',  # Exact match
            'artist': 'Daft Punk',
            'album': 'Random Access Memories',
            'duration_ms': 248000,
            'isrc': 'USCOLUMN123456'
        },
        {
            'title': 'Get Lucky (Radio Edit)',  # Different version
            'artist': 'Daft Punk',
            'album': 'Random Access Memories',
            'duration_ms': 180000,
            'isrc': 'DIFFERENT_ISRC'
        }
    ]

    match = matcher.match_tracks(source, candidates)

    assert match is not None, "Should find match"
    assert match['isrc'] == 'USCOLUMN123456', "Should match by ISRC"
    assert match['duration_ms'] == 248000, "Should return correct version"

    print("✓ ISRC matching works perfectly!")


def test_fuzzy_matching_exact():
    """Test fuzzy matching with exact metadata."""
    print("Testing: Fuzzy matching (exact metadata)...")

    matcher = TrackMatcher()

    source = {
        'title': 'Bohemian Rhapsody',
        'artist': 'Queen',
        'album': 'A Night at the Opera',
        'duration_ms': 354000
    }

    candidates = [
        {
            'title': 'Bohemian Rhapsody',
            'artist': 'Queen',
            'album': 'A Night at the Opera',
            'duration_ms': 354000
        }
    ]

    match = matcher.match_tracks(source, candidates)

    assert match is not None, "Should find match"

    score = matcher.compute_similarity(source, match)
    assert score > 95, f"Exact match should score >95, got {score}"

    print(f"✓ Exact metadata match score: {score:.2f}")


def test_fuzzy_matching_typos():
    """Test fuzzy matching with typos."""
    print("Testing: Fuzzy matching (with typos)...")

    matcher = TrackMatcher()

    source = {
        'title': 'Stairway to Heaven',
        'artist': 'Led Zeppelin',
        'album': 'Led Zeppelin IV',
        'duration_ms': 482000
    }

    candidates = [
        {
            'title': 'Stairway To Heaven',  # Different capitalization
            'artist': 'Led Zepellin',  # Typo in artist
            'album': 'Led Zeppelin IV',
            'duration_ms': 482000
        }
    ]

    match = matcher.match_tracks(source, candidates)

    assert match is not None, "Should find match despite typos"

    score = matcher.compute_similarity(source, match)
    assert score > 85, f"Match with minor typos should score >85, got {score}"

    print(f"✓ Fuzzy match with typos score: {score:.2f}")


def test_normalization():
    """Test string normalization."""
    print("Testing: String normalization...")

    matcher = TrackMatcher()

    # Test accent removal
    assert matcher.normalize_string('Café') == 'cafe'

    # Test punctuation removal
    assert matcher.normalize_string("Don't Stop Me Now") == 'dont stop me now'

    # Test suffix removal (parentheses removed as punctuation, then suffix removed)
    # 'Song Name (Remastered)' → 'song name remastered' → 'song name'
    result = matcher.normalize_string('Song Name (Remastered)')
    assert 'song name' in result, f"Expected 'song name' in result, got: {result}"
    assert 'remaster' not in result, f"Suffix 'remaster' should be removed, got: {result}"

    # Test whitespace normalization
    assert matcher.normalize_string('Too   Many    Spaces') == 'too many spaces'

    print("✓ String normalization works!")


def test_different_versions():
    """Test matching different versions of the same song."""
    print("Testing: Different versions (should NOT match)...")

    matcher = TrackMatcher()

    source = {
        'title': 'Smells Like Teen Spirit',
        'artist': 'Nirvana',
        'album': 'Nevermind',
        'duration_ms': 301000
    }

    candidates = [
        {
            'title': 'Smells Like Teen Spirit (Live)',  # Live version
            'artist': 'Nirvana',
            'album': 'MTV Unplugged',
            'duration_ms': 280000  # Different duration
        }
    ]

    score = matcher.compute_similarity(source, candidates[0])

    # Should still match but with lower score
    assert score < 90, f"Different versions should score <90, got {score}"
    assert score > 70, f"But should still have some similarity, got {score}"

    print(f"✓ Different version match score: {score:.2f} (correctly lower)")


def test_no_match():
    """Test when there's no good match."""
    print("Testing: No match scenario...")

    matcher = TrackMatcher()

    source = {
        'title': 'Yesterday',
        'artist': 'The Beatles',
        'album': 'Help!',
        'duration_ms': 125000
    }

    candidates = [
        {
            'title': 'Tomorrow',
            'artist': 'The Rolling Stones',
            'album': 'Different Album',
            'duration_ms': 200000
        }
    ]

    match = matcher.match_tracks(source, candidates)

    assert match is None, "Should not match completely different songs"

    print("✓ Correctly rejects bad matches!")


def test_best_match_selection():
    """Test selecting the best match from multiple candidates."""
    print("Testing: Best match selection...")

    matcher = TrackMatcher()

    source = {
        'title': 'Imagine',
        'artist': 'John Lennon',
        'album': 'Imagine',
        'duration_ms': 183000
    }

    candidates = [
        {
            'title': 'Imagine (Remastered)',
            'artist': 'John Lennon',
            'album': 'Imagine',
            'duration_ms': 183000  # Perfect match
        },
        {
            'title': 'Imagine',
            'artist': 'John Lennon Cover Band',
            'album': 'Covers',
            'duration_ms': 180000  # Close but not as good
        },
        {
            'title': 'Imagine',
            'artist': 'John Lennon',
            'album': 'Greatest Hits',
            'duration_ms': 183000  # Also good
        }
    ]

    match = matcher.match_tracks(source, candidates)

    assert match is not None
    # Should pick first or third (both have exact duration)
    assert match['duration_ms'] == 183000
    assert 'Cover Band' not in match['artist']

    print("✓ Selects best match from candidates!")


def test_duration_similarity():
    """Test duration-based similarity scoring."""
    print("Testing: Duration similarity...")

    matcher = TrackMatcher()

    track1 = {'title': 'Song', 'artist': 'Artist', 'album': 'Album', 'duration_ms': 180000}  # 3:00
    track2 = {'title': 'Song', 'artist': 'Artist', 'album': 'Album', 'duration_ms': 181000}  # 3:01

    score = matcher.compute_similarity(track1, track2)

    # 1 second difference should have minimal impact
    assert score > 95, f"1 second difference should score >95, got {score}"

    track3 = {'title': 'Song', 'artist': 'Artist', 'album': 'Album', 'duration_ms': 200000}  # 3:20

    score = matcher.compute_similarity(track1, track3)

    # 20 second difference should lower the score
    assert score < 95, f"20 second difference should score <95, got {score}"

    print("✓ Duration similarity works!")


def test_find_duplicates():
    """Test duplicate detection."""
    print("Testing: Duplicate detection...")

    matcher = TrackMatcher()

    tracks = [
        {'title': 'Imagine', 'artist': 'John Lennon', 'album': 'Imagine', 'duration_ms': 183000},
        {'title': 'Imagine', 'artist': 'John Lennon', 'album': 'Imagine - Remastered', 'duration_ms': 183000},  # Should be duplicate
        {'title': 'Yesterday', 'artist': 'The Beatles', 'album': 'Help!', 'duration_ms': 125000},
        {'title': 'Let It Be', 'artist': 'The Beatles', 'album': 'Let It Be', 'duration_ms': 243000},
        {'title': 'Let It Be', 'artist': 'The Beatles', 'album': 'Let It Be', 'duration_ms': 243000},  # Exact duplicate
    ]

    duplicates = matcher.find_duplicates(tracks, threshold=95.0)

    assert len(duplicates) >= 1, f"Should find at least 1 duplicate group, found {len(duplicates)}"

    # Check that we found the exact duplicate at least
    has_exact_dup = any(len(group) >= 2 for group in duplicates)
    assert has_exact_dup, "Should find at least one group with 2+ tracks"

    print(f"✓ Found {len(duplicates)} duplicate group(s)!")


def test_threshold_adjustment():
    """Test custom threshold setting."""
    print("Testing: Custom threshold...")

    # Strict matcher
    strict_matcher = TrackMatcher(threshold=95.0)

    # Lenient matcher
    lenient_matcher = TrackMatcher(threshold=75.0)

    source = {
        'title': 'Test Song',
        'artist': 'Test Artist',
        'album': 'Test Album',
        'duration_ms': 180000
    }

    candidate = {
        'title': 'Test Song (Radio Edit)',
        'artist': 'Test Artist',
        'album': 'Test Album - Deluxe',
        'duration_ms': 160000
    }

    score = strict_matcher.compute_similarity(source, candidate)

    strict_match = strict_matcher.is_confident_match(source, candidate)
    lenient_match = lenient_matcher.is_confident_match(source, candidate)

    print(f"  Match score: {score:.2f}")
    print(f"  Strict matcher (threshold 95): {strict_match}")
    print(f"  Lenient matcher (threshold 75): {lenient_match}")

    assert not strict_match, "Strict matcher should reject this match"
    assert lenient_match, "Lenient matcher should accept this match"

    print("✓ Custom thresholds work!")


def run_all_tests():
    """Run all matcher tests."""
    print("=" * 70)
    print("Running Track Matcher Tests")
    print("=" * 70)
    print()

    tests = [
        test_isrc_matching,
        test_fuzzy_matching_exact,
        test_fuzzy_matching_typos,
        test_normalization,
        test_different_versions,
        test_no_match,
        test_best_match_selection,
        test_duration_similarity,
        test_find_duplicates,
        test_threshold_adjustment,
    ]

    for test in tests:
        test()
        print()

    print("=" * 70)
    print(f"🎉 All {len(tests)} matcher tests passed!")
    print("=" * 70)


if __name__ == '__main__':
    run_all_tests()
