"""Crawler modules for Korean and Japanese news outlets."""

from .base import BaseCrawler
from .jungang import JungangCrawler
from .yomiuri import YomiuriCrawler

__all__ = ["BaseCrawler", "JungangCrawler", "YomiuriCrawler"]
