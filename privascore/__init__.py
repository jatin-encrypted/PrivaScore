"""PrivaScore: privacy policy risk assessment.

Modules
  text       normalisation + sentence segmentation (shared with the gold-set tools)
  flags      flag definitions + search-term retrieval
  scoring    Privacy Risk Index and Disclosure Quality score
  verifier   checks that LLM-cited quotes really occur in the policy
  llm        provider-agnostic LLM clients (mock, Gemini, Groq)
  extractor  per-flag LLM extraction with verification and caching
  evaluate   compare an extraction run with the human gold labels
"""
__version__ = "0.1.0"
