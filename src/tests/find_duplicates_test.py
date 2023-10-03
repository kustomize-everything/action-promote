import pytest
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import validate

def test_find_duplicates_basic():
    images = [
        {'name': 'img1'},
        {'name': 'img2'},
        {'name': 'img1'}
    ]
    expected = {'img1'}

    duplicates = validate.find_duplicates(images, 'name')

    assert duplicates == expected

def test_find_duplicates_empty():
    images = []
    expected = set()

    duplicates = validate.find_duplicates(images, 'name')

    assert duplicates == expected

def test_find_duplicates_missing_field():
    images = [
        {'name': 'img1'},
        {'tag': 'v1.0'}
    ]
    expected = set()

    duplicates = validate.find_duplicates(images, 'name')

    assert duplicates == expected
