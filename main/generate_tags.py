import ollama
from pathlib import Path
import json
import time
import re
import requests
import html
from collections import defaultdict
import urllib3


########################################################################
########################## Searching Tags ##############################
########################################################################
# SSL 경고 비활성화
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ============================================================================
# PubMed Literature Search Functions
# ============================================================================

DEFAULT_TOPIC_KEYWORDS = [
    # Host / pathogenicity
    "host range", "host specificity", "host colonization",
    "pathogenicity", "virulence", "infection", "disease", "clinical isolate",
    "commensal", "opportunistic pathogen",
    
    # Niche / habitat / ecology
    "gut microbiota", "intestinal colonization", "microbiome",
    "ecology", "habitat", "environmental isolate", "soil", "water",
    
    # Growth / physiology
    "growth conditions", "cultivation", "temperature", "pH", "oxygen",
    "aerobic", "anaerobic", "microaerophilic",
    
    # Resistance / survival traits
    "antibiotic resistance", "multidrug resistant", "biofilm",
    "stress tolerance", "acid tolerance", "bile tolerance",
]


def search_and_fetch_literature(organism_name, strain=None, topic_keywords=None,
                                num_abstracts=10, num_fulltexts=5, api_email=None):
    """Search PubMed and fetch abstracts/full texts with smart PMC-aware collection"""
    
    if not topic_keywords:
        topic_keywords = DEFAULT_TOPIC_KEYWORDS
    
    search_log = []
    pmid_info = defaultdict(lambda: {"topics": set(), "has_pmc": False})
    
    # Build and execute queries
    base_terms = [f'"{organism_name}"[Title/Abstract]']
    if strain and strain.strip():
        base_terms.append(f'"{organism_name} {strain.strip()}"[Title/Abstract]')
        base_terms.append(f'"{strain.strip()}"[Title/Abstract]')
    
    base_query = "(" + " OR ".join(base_terms) + ")"
    
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    
    # Collect more PMIDs initially (we'll filter by PMC availability later)
    max_per_topic = 20  # Increased to get more candidates
    for keyword in topic_keywords:
        if not keyword.strip():
            continue
        query = f'{base_query} AND "{keyword.strip()}"[Title/Abstract]'

        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_per_topic,
            "retmode": "json",
        }
        if api_email:
            params["email"] = api_email
        
        try:
            response = requests.get(search_url, params=params, verify=False)
            pmids = response.json().get("esearchresult", {}).get("idlist", [])
            search_log.append(f"[{keyword}] Found {len(pmids)} PMIDs")
            
            for pmid in pmids:
                pmid_info[pmid]["topics"].add(keyword)
            
            time.sleep(0.34)
        except Exception as e:
            search_log.append(f"Error searching '{keyword}': {e}")
    
    if not pmid_info:
        search_log.append("No PMIDs found")
        return [], [], [], search_log
    
    search_log.append(f"Total unique PMIDs collected: {len(pmid_info)}")
    
    # Check PMC availability for all collected PMIDs (batch check with PMC ID caching)
    all_pmids = list(pmid_info.keys())
    pmc_available_pmids = []
    
    search_log.append("Checking PMC availability...")
    batch_size = 100
    for i in range(0, len(all_pmids), batch_size):
        batch_pmids = all_pmids[i:i+batch_size]
        try:
            link_response = requests.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi",
                params={
                    "dbfrom": "pubmed",
                    "db": "pmc",
                    "id": ",".join(batch_pmids),
                    "retmode": "json"
                },
                timeout=30,
                verify=False
            )
            link_data = link_response.json()
            
            if "linksets" in link_data:
                for linkset in link_data["linksets"]:
                    pmid = str(linkset.get("ids", [None])[0])
                    if pmid and "linksetdbs" in linkset:
                        for ldb in linkset["linksetdbs"]:
                            if ldb.get("dbto") == "pmc" and ldb.get("links"):
                                links = ldb.get("links", [])
                                if links:
                                    # Cache PMC ID
                                    pmc_id = str(links[0]) if isinstance(links[0], (int, str)) else links[0].get("id")
                                    pmid_info[pmid]["has_pmc"] = True
                                    pmid_info[pmid]["pmc_id"] = pmc_id
                                    pmc_available_pmids.append(pmid)
                                break
            
            time.sleep(0.34)
        except Exception as e:
            search_log.append(f"Error checking PMC availability: {e}")
    
    search_log.append(f"PMIDs with PMC full-text: {len(pmc_available_pmids)}")
    
    # Select PMIDs: prioritize PMC-available for full-text requests
    if num_fulltexts > 0:
        # Sort: PMC available first, then by topic coverage
        all_pmid_list = list(pmid_info.keys())
        selected_pmids = sorted(
            all_pmid_list,
            key=lambda p: (
                pmid_info[p]["has_pmc"],  # PMC available first
                len(pmid_info[p]["topics"]),  # More topics better
                -int(p)  # Recent papers
            ),
            reverse=True
        )[:max(num_abstracts, num_fulltexts * 3)]  # Get enough candidates
        
        # Debug log
        pmc_in_selected = sum(1 for p in selected_pmids if pmid_info[p]["has_pmc"])
        search_log.append(f"Selected {len(selected_pmids)} PMIDs ({pmc_in_selected} with PMC)")
    else:
        # No full-text needed: just prioritize topic coverage
        selected_pmids = sorted(
            pmid_info.keys(),
            key=lambda p: (len(pmid_info[p]["topics"]), -int(p)),
            reverse=True
        )[:num_abstracts]
        search_log.append(f"Selected {len(selected_pmids)} PMIDs for fetching")
    
    # Fetch abstracts
    abstracts = []
    if num_abstracts > 0:
        try:
            fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            response = requests.get(fetch_url, params={
                "db": "pubmed",
                "id": ",".join(selected_pmids[:num_abstracts * 2]),  # Fetch extra in case some are empty
                "retmode": "xml"
            }, timeout=30, verify=False)
            
            abstract_matches = re.findall(
                r"<AbstractText[^>]*>(.*?)</AbstractText>",
                response.text,
                re.DOTALL
            )
            
            for abstract in abstract_matches:
                clean = re.sub(r"<[^>]+>", " ", abstract)
                clean = re.sub(r"\s+", " ", clean).strip()
                if len(clean) > 100:
                    abstracts.append(clean)
                    if len(abstracts) >= num_abstracts:
                        break
            
            search_log.append(f"Abstracts collected: {len(abstracts)}/{num_abstracts}")
        except Exception as e:
            search_log.append(f"Error fetching abstracts: {e}")
    
    # Fetch full texts from PMC (only from PMC-available PMIDs)
    full_texts = []
    if num_fulltexts > 0:
        pmc_pmids = [p for p in selected_pmids if pmid_info[p]["has_pmc"]]
        search_log.append(f"Attempting full-text from {len(pmc_pmids)} PMC-available papers")
        
        for pmid in pmc_pmids:
            if len(full_texts) >= num_fulltexts:
                break
                
            try:
                # Use cached PMC ID from batch check
                pmc_id = pmid_info[pmid].get("pmc_id")
                
                if not pmc_id:
                    search_log.append(f"✗ PMID {pmid}: No cached PMC ID")
                    continue
                
                search_log.append(f"→ PMID {pmid} → PMC {pmc_id}")
                
                # Fetch full text
                pmc_response = requests.get(
                    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                    params={"db": "pmc", "id": pmc_id, "retmode": "xml"},
                    timeout=60,
                    verify=False
                )
                
                # Try multiple body patterns
                body_match = re.search(r"<body[^>]*>(.*?)</body>", pmc_response.text, re.DOTALL)
                if not body_match:
                    # Try alternative pattern
                    body_match = re.search(r"<abstract[^>]*>(.*?)</abstract>", pmc_response.text, re.DOTALL)
                
                if body_match:
                    clean = re.sub(r"<[^>]+>", " ", body_match.group(1))
                    clean = re.sub(r"\s+", " ", clean).strip()
                    
                    if len(clean) > 500:
                        full_texts.append(clean)
                        search_log.append(f"✓ PMC {pmc_id}: {len(clean):,} chars")
                    else:
                        search_log.append(f"✗ PMC {pmc_id}: Content too short ({len(clean)} chars)")
                else:
                    # Check if response has any content
                    resp_preview = pmc_response.text[:200] if pmc_response.text else "Empty response"
                    search_log.append(f"✗ PMC {pmc_id}: No body tag found. Response preview: {resp_preview}")
                
                time.sleep(0.5)
            except Exception as e:
                search_log.append(f"✗ PMID {pmid} error: {e}")
        
        search_log.append(f"Full texts collected: {len(full_texts)}/{num_fulltexts}")
    
    return selected_pmids, abstracts, full_texts, search_log

# ============================================================================
# Text Processing Functions
# ============================================================================

def clean_and_split_text(text):
    """Clean text and split into sentences"""
    if not text:
        return []
    
    # Remove JavaScript code
    text = re.sub(r'<script[^>]*>.*?</script>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove inline JavaScript and CSSA
    text = re.sub(r'on\w+\s*=\s*["\'][^"\']*["\']', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'style\s*=\s*["\'][^"\']*["\']', ' ', text, flags=re.IGNORECASE)
    
    # Remove JSON/JavaScript objects (like RLCONF, etc.)
    text = re.sub(r'\w+\s*=\s*\{[^}]*\}[;,]?', ' ', text)
    text = re.sub(r'document\.\w+[^;]*;', ' ', text)
    
    # Remove HTML comments
    text = re.sub(r'<!--.*?-->', ' ', text, flags=re.DOTALL)
    
    # Remove remaining HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # Clean HTML entities and artifacts
    text = html.unescape(text)
    text = re.sub(r"[ \t\u00A0\u2000-\u200B\u3000]+", " ", text)
    text = re.sub(r"E\.\s*\n+\s*coli", "E. coli", text, flags=re.IGNORECASE)
    text = re.sub(r"TABLE\s+\d+\s+", " ", text, flags=re.IGNORECASE)
    
    # Remove common web artifacts
    text = re.sub(r'\b(getElementById|className|innerHTML|addEventListener)\b', ' ', text)
    text = re.sub(r'[{\[}\]]+', ' ', text)  # Remove standalone brackets
    
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text).strip()
    
    # Split into sentences
    sentences = re.split(r'(?<=[\.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def is_protocol_sentence(sentence):
    """Check if sentence describes experimental methods"""
    s_lower = sentence.lower()
    
    # Protocol keywords
    if any(kw in s_lower for kw in [
        "incubated", "centrifuged", "cultured", "harvested", "washed",
        "inoculated", "pipetted", "lysed", "extracted",
        "broth", "agar", "medium", "rpm", "spectrophotometer"
    ]):
        return True
    
    # Units and measurements
    if re.search(r"\b\d+(\.\d+)?\s*(°c|mg/ml|µl|ml|min|hr|hours|od\d{3})\b", s_lower):
        return True
    
    # Numbers with ± or %
    if len(re.findall(r"\d", sentence)) >= 8 and ("±" in sentence or "%" in sentence):
        return True
    
    return False


def process_corpus(text, organism_name, remove_protocols=True, remove_duplicates=True, 
                   remove_incomplete=True, min_sentence_length=40, max_chars=None):
    """Complete text processing pipeline with optional length limit on final corpus"""
    
    sentences = clean_and_split_text(text)
    
    # Filter protocols
    if remove_protocols:
        sentences = [s for s in sentences if not is_protocol_sentence(s)]
    
    # Remove short sentences
    sentences = [s for s in sentences if len(s) >= min_sentence_length]
    
    # Remove incomplete sentences
    if remove_incomplete:
        sentences = [s for s in sentences if s.endswith((".", "?", "!"))]
    
    # Remove duplicates
    if remove_duplicates:
        seen = set()
        unique_sentences = []
        for s in sentences:
            norm = re.sub(r"\s+", " ", s.lower())
            if norm not in seen:
                seen.add(norm)
                unique_sentences.append(s)
        sentences = unique_sentences
    
    # Apply max_chars limit to final cleaned corpus
    if max_chars:
        corpus = ""
        for sent in sentences:
            if len(corpus) + len(sent) + 1 > max_chars:
                break
            corpus += sent + " "
        return corpus.strip()
    
    return " ".join(sentences)

# ============================================================================
# Organism-Specific Extraction
# ============================================================================

def extract_organism_corpus(abstracts, full_texts, organism_name, max_chars=15000):
    """Extract organism-specific content from literature"""
    
    # Build organism aliases
    aliases = {organism_name.lower()}
    parts = organism_name.split()
    if len(parts) >= 2:
        genus, species = parts[0], parts[1]
        aliases.add(f"{genus[0]}. {species}".lower())
        aliases.add(species.lower())
    
    alias_pattern = re.compile(
        "(" + "|".join(re.escape(a) for a in aliases) + ")",
        re.IGNORECASE
    )
    
    # Process all documents
    blocks = []
    for text in (abstracts or []) + (full_texts or []):
        sentences = clean_and_split_text(text)
        
        # Find sentences mentioning organism
        for i, sent in enumerate(sentences):
            if alias_pattern.search(sent.lower()):
                # Include context (previous and next sentence)
                start = max(0, i - 1)
                end = min(len(sentences), i + 2)
                block = " ".join(sentences[start:end])
                if len(block) >= 150:
                    blocks.append(block)
    
    # Prioritize longer blocks and build corpus
    blocks.sort(key=len, reverse=True)
    corpus = ""
    for block in blocks:
        if max_chars and len(corpus) + len(block) + 2 > max_chars:
            continue
        corpus += block + "\n\n"
    
    return corpus.strip()


# ============================================================================
# Web Resource Search Functions
# ============================================================================

def search_wikipedia(organism_name):
    """Search Wikipedia for organism information"""
    log = []
    try:
        log.append(f"Wikipedia 검색 시작: {organism_name}")
        search_url = "https://en.wikipedia.org/w/api.php"
        search_params = {
            'action': 'query',
            'format': 'json',
            'list': 'search',
            'srsearch': organism_name,
            'srlimit': 1
        }
        
        headers = {
            'User-Agent': 'GeneExpBot/1.0 (Research Project; Contact: research@example.com)'
        }
        
        log.append(f"Wikipedia API 요청: {search_params}")
        search_response = requests.get(search_url, params=search_params, headers=headers, timeout=10, verify=False)
        search_data = search_response.json()
        
        if search_data.get('query', {}).get('search'):
            page_title = search_data['query']['search'][0]['title']
            log.append(f"Wikipedia 페이지 발견: {page_title}")
            
            # Fetch full page content
            content_params = {
                'action': 'query',
                'format': 'json',
                'titles': page_title,
                'prop': 'extracts',
                'explaintext': True,
                'exsectionformat': 'plain'
            }
            
            content_response = requests.get(search_url, params=content_params, headers=headers, timeout=10, verify=False)
            content_data = content_response.json()
            
            pages = content_data.get('query', {}).get('pages', {})
            if pages:
                page_id = list(pages.keys())[0]
                page_info = pages[page_id]
                extract_content = page_info.get('extract', '')
                
                if extract_content:
                    log.append(f"Wikipedia 내용 수집 완료: {len(extract_content)}자")
                    return {
                        'title': page_info.get('title', ''),
                        'extract': extract_content,
                        'url': f"https://en.wikipedia.org/wiki/{page_title.replace(' ', '_')}",
                        'source': 'Wikipedia'
                    }, log
                else:
                    log.append("Wikipedia 페이지에 내용이 없음")
        else:
            log.append("Wikipedia 검색 결과 없음")
    except Exception as e:
        log.append(f"Wikipedia 검색 오류: {e}")
    
    return None, log


def search_microbewiki(organism_name):
    """Search MicrobeWiki for organism information"""
    log = []
    try:
        log.append(f"MicrobeWiki 검색 시작: {organism_name}")
        genus = organism_name.split()[0] if ' ' in organism_name else organism_name
        
        # Try exact organism name first, then genus
        search_terms = [organism_name.replace(' ', '_'), genus]
        log.append(f"MicrobeWiki 검색어 목록: {search_terms}")
        
        for search_term in search_terms:
            microbewiki_url = f"https://microbewiki.kenyon.edu/index.php/{search_term}"
            log.append(f"MicrobeWiki URL 시도: {microbewiki_url}")
            
            try:
                response = requests.get(microbewiki_url, timeout=10, verify=False)
                log.append(f"MicrobeWiki 응답 코드: {response.status_code}")
                
                if response.status_code == 200:
                    content = response.text
                    
                    # Check if it's a real page (not a 404 or redirect)
                    if 'There is currently no text in this page' not in content:
                        # Extract text from HTML with aggressive cleaning
                        # Remove scripts and styles first
                        text_content = re.sub(r'<script[^>]*>.*?</script>', ' ', content, flags=re.DOTALL | re.IGNORECASE)
                        text_content = re.sub(r'<style[^>]*>.*?</style>', ' ', text_content, flags=re.DOTALL | re.IGNORECASE)
                        
                        # Remove HTML tags
                        text_content = re.sub(r'<[^>]+>', ' ', text_content)
                        
                        # Clean up whitespace
                        text_content = re.sub(r'\s+', ' ', text_content).strip()
                        
                        if len(text_content) > 500:  # Ensure meaningful content
                            log.append(f"MicrobeWiki 내용 수집 완료: {len(text_content)}자")
                            return {
                                'url': microbewiki_url,
                                'content': text_content,
                                'search_term': search_term,
                                'source': 'MicrobeWiki'
                            }, log
                        else:
                            log.append(f"MicrobeWiki 내용이 너무 짧음: {len(text_content)}자")
                    else:
                        log.append(f"MicrobeWiki 페이지가 비어있음")
            except requests.exceptions.Timeout:
                log.append(f"MicrobeWiki 타임아웃: {search_term}")
                continue
            except Exception as e:
                log.append(f"MicrobeWiki 오류 ({search_term}): {e}")
                continue
        
        log.append("MicrobeWiki에서 유효한 정보를 찾을 수 없음")
    except Exception as e:
        log.append(f"MicrobeWiki 검색 중 예외: {e}")
    
    return None, log


def search_web_resources(organism_name):
    """Search multiple web resources for organism information"""
    web_content = {}
    search_log = []
    
    search_log.append("=" * 60)
    search_log.append(f"웹 자료 검색 시작: {organism_name}")
    search_log.append("=" * 60)
    
    # Wikipedia search
    print("   Searching Wikipedia...")
    wiki_result, wiki_log = search_wikipedia(organism_name)
    search_log.extend(wiki_log)
    if wiki_result:
        web_content['wikipedia'] = wiki_result
        chars = len(wiki_result.get('extract', ''))
        search_log.append(f"✓ Wikipedia: {chars:,} chars")
        print(f"   ✓ Wikipedia: {chars:,} chars")
    else:
        search_log.append("✗ Wikipedia: No results")
        print("   ✗ Wikipedia: No results")
    
    time.sleep(1)
    
    # MicrobeWiki search
    print("   Searching MicrobeWiki...")
    microbewiki_result, microbewiki_log = search_microbewiki(organism_name)
    search_log.extend(microbewiki_log)
    if microbewiki_result:
        web_content['microbewiki'] = microbewiki_result
        chars = len(microbewiki_result.get('content', ''))
        search_log.append(f"✓ MicrobeWiki: {chars:,} chars")
        print(f"   ✓ MicrobeWiki: {chars:,} chars")
    else:
        search_log.append("✗ MicrobeWiki: No results")
        print("   ✗ MicrobeWiki: No results")
    
    time.sleep(1)
    
    total_content_length = sum(
        len(str(content.get('extract', content.get('content', '')))) 
        for content in web_content.values()
    )
    search_log.append("=" * 60)
    search_log.append(f"웹 검색 완료: {total_content_length:,} chars from {len(web_content)} sources")
    search_log.append("=" * 60)
    
    return web_content, search_log

# ============================================================================
# Main Pipeline Function
# ============================================================================

def create_tagging_corpus(
    organism_name,
    strain=None,
    topic_keywords=None,
    num_abstracts=10,
    num_fulltexts=5,
    max_corpus_chars=15000,
    include_web_resources=True,
    api_email=None,
):
    """
    Complete pipeline: search literature + web → extract organism content → clean for tagging
    
    Parameters:
    -----------
    organism_name : str
        Target organism (e.g., "Escherichia coli")
    strain : str, optional
        Strain name (e.g., "K-12 substr. MG1655")
    topic_keywords : list, optional
        Topic keywords for search
    num_abstracts : int
        Number of abstracts to collect (default: 10)
    num_fulltexts : int
        Number of full texts to collect (default: 5)
    max_corpus_chars : int
        Max corpus size (default: 15000)
    include_web_resources : bool
        Include Wikipedia and MicrobeWiki (default: True)
    api_email : str, optional
        NCBI API email
    
    Returns:
    --------
    dict with keys: corpus, pmids, abstracts, full_texts, web_content, stats, logs
    """
    
    print("=" * 70)
    print(f"Creating Tagging Corpus for: {organism_name}")
    if strain:
        print(f"Strain: {strain}")
    print("=" * 70)
    
    # Step 1: Search and fetch literature
    print("\n[1/4] Searching and fetching literature...")
    pmids, abstracts, full_texts, lit_logs = search_and_fetch_literature(
        organism_name=organism_name,
        strain=strain,
        topic_keywords=topic_keywords,
        num_abstracts=num_abstracts,
        num_fulltexts=num_fulltexts,
        api_email=api_email,
    )
    print(f"   PMIDs: {len(pmids)}, Abstracts: {len(abstracts)}, Full texts: {len(full_texts)}")
    
    # Step 2: Search web resources
    web_content = {}
    web_logs = []
    if include_web_resources:
        print("\n[2/4] Searching web resources (Wikipedia, MicrobeWiki)...")
        web_content, web_logs = search_web_resources(organism_name)
        print(f"   Web sources: {len(web_content)}")
    else:
        print("\n[2/4] Skipping web resources...")
    
    # Combine all text sources
    all_texts = abstracts + full_texts
    for source, content in web_content.items():
        if isinstance(content, dict):
            text = content.get('extract', content.get('content', ''))
            if text:
                all_texts.append(text)
    
    if not all_texts:
        print("   No content found. Exiting.")
        return {
            "corpus": "",
            "pmids": pmids,
            "abstracts": abstracts,
            "full_texts": full_texts,
            "web_content": web_content,
            "stats": {},
            "logs": lit_logs + web_logs,
        }
    
    # Step 3: Extract organism-specific content
    print(f"\n[3/4] Extracting organism-specific content from {len(all_texts)} sources...")
    raw_corpus = extract_organism_corpus(
        abstracts=abstracts,
        full_texts=full_texts + [content.get('extract', content.get('content', '')) 
                                  for content in web_content.values() if isinstance(content, dict)],
        organism_name=organism_name,
        max_chars=None,  # Don't limit raw corpus
    )
    print(f"   Raw corpus: {len(raw_corpus)} chars")
    
    # Step 4: Clean corpus and apply max_corpus_chars limit
    print("\n[4/4] Cleaning corpus (remove protocols, duplicates, incomplete sentences)...")
    print(f"   Target max length: {max_corpus_chars:,} chars")
    corpus = process_corpus(
        text=raw_corpus,
        organism_name=organism_name,
        remove_protocols=True,
        remove_duplicates=True,
        remove_incomplete=True,
        max_chars=max_corpus_chars,
    )
    
    reduction = ((len(raw_corpus) - len(corpus)) / len(raw_corpus) * 100) if raw_corpus else 0
    truncated = " (truncated to max)" if max_corpus_chars and len(corpus) >= max_corpus_chars * 0.95 else ""
    print(f"   Final corpus: {len(corpus):,} chars ({reduction:.1f}% reduction){truncated}")
    
    print("\n" + "=" * 70)
    
    return {
        "corpus": corpus,
        "pmids": pmids,
        "abstracts": abstracts,
        "full_texts": full_texts,
        "web_content": web_content,
        "stats": {
            "pmids_count": len(pmids),
            "abstracts_count": len(abstracts),
            "full_texts_count": len(full_texts),
            "web_sources_count": len(web_content),
            "raw_corpus_chars": len(raw_corpus),
            "final_corpus_chars": len(corpus),
            "reduction_percent": reduction,
        },
        "logs": lit_logs + web_logs,
    }

def prompt_generation(organism, strain, search_data):
   prompt = f"""You are an expert microbiologist. Your task is to extract a set of descriptive, non-redundant **organism-level tags** that together provide a detailed, genome-wide biological description of the target: **{organism}** (strain: **{strain}**).

## Target Organism:
{organism} {strain}

## Literature and Web Data:
{search_data}

RULES:
1. Use only information explicitly stated in the text.
2. Do not infer, generalize, or add external knowledge.
3. Do NOT include any trait, property, disease, toxin, phenotype, serotype, or behavior that refers to:
   - other strains,
   - pathotypes,
   - serotypes,
   - clinical variants,
   - probiotic strains,
   - or any organism other than the exact target.
   (Completely exclude them, even with qualifiers like “some strains”.)
4. If a trait applies only under experimental or special conditions, include the condition in the tag.
5. Each tag must express exactly one biological characteristic (taxonomy, morphology, membrane structure, physiology, respiration, growth conditions, etc.).
6. Remove redundancy. Do not merge unrelated ideas.

### OUTPUT FORMAT (strict):
output must be in valid JSON format as shown below, with a single key "tags" containing a list of tags.
"""+"""
```json
{
  "tags": ["tag1", "tag2", "..."]
}
"""
   return prompt
import ollama
import json
# response = ollama.chat(model = model, messages = [{
#     'role':'user',
#     'content': "Describe about Genome"
# }])
# print(response['message']['content'])



def parse_tags(response_text):
    """Parse response with strict JSON parsing and robust fallback."""
    text = response_text.strip()

    # Try to find JSON object in the text
    json_match = re.search(r'\{[^}]*"tags"\s*:\s*\[[^\]]*\][^}]*\}', text, re.DOTALL)
    if json_match:
        text = json_match.group(0)
    
    # Attempt JSON parsing
    obj = json.loads(text)
    if isinstance(obj, dict) and 'tags' in obj:
        raw_tags = obj['tags']
        if not isinstance(raw_tags, list):
            print(f"Warning: 'tags' is not a list: {type(raw_tags)}")
            return []
        
        # Clean and deduplicate tags
        tags = []
        seen = set()
        for t in raw_tags:
            if not t:  # Skip empty
                continue
            tag_str = str(t).strip()
            if not tag_str:
                continue
            key = tag_str.lower()
            if key not in seen:
                seen.add(key)
                tags.append(tag_str)
        return tags
    
#############################################################################

def searching_tags(organism, strain, sub_strain, num_abstracts=10, num_fulltexts=5, max_corpus_chars=15000):
    
    model = 'kronos483/Llama-3.2-3B-PubMed:latest'

    substr = " substr. ".join([strain, sub_strain])

    result = create_tagging_corpus(
        organism_name=organism,
        strain=substr,
        num_abstracts=num_abstracts,
        num_fulltexts=num_fulltexts,
        max_corpus_chars=max_corpus_chars,
        include_web_resources=True,  # Wikipedia + MicrobeWiki
        )
    
    prompt = prompt_generation(organism, substr, result['corpus'])
    print('Prompt Generated:')
    print(prompt)
    tag_list = []
    for i in range(3):
        n = 0
        while n <= 5:    
            try:
                response = ollama.chat(model = model, messages = [{
                'role':'user',
                'content': prompt
                }])
                tags = parse_tags(response['message']['content'])
                
                if len(tags) > 0:
                    tag_list.append(tags)
                    print(f'Response Received:{tags}')
                    break
                else:
                    n += 1
                    continue
            except Exception as e:
                n += 1
                print(f"Error during chat or parsing: {e}")
                print("Retrying...")


    tags_flat = []
    _seen = set()
    for entry in tag_list:
        if isinstance(entry, (list, tuple, set)):
            iterable = entry
        else:
            iterable = [entry]
        for t in iterable:
            if t is None:
                continue
            s = str(t).strip()
            key = s.lower()
            if key not in _seen:
                _seen.add(key)
                tags_flat.append(s)
    print(f'process completed: total {len(tags_flat)} tags extracted.')

    return tags_flat


####################################################################
########################## Collect Tags ############################
####################################################################

model = 'kronos483/Llama-3.2-3B-PubMed:latest'

def chunk_products(products, chunk_size=100):
    """Split products into chunks of specified size"""
    for i in range(0, len(products), chunk_size):
        yield products[i:i + chunk_size]

def prompt_gen_tags(products_chunk):
    products_str = "\n".join(products_chunk)
    prompt = f"""
You are an expert microbial genome annotator.

Below is a list of protein product annotations extracted from coding sequences (CDS) in a bacterial genome:
{products_str}
""" + """

Goal:
List concise functional tags that describe distinctive biological capabilities or ecological traits specific to this genome, excluding functions common to most bacteria.

Guidelines:
- Use only evidence clearly supported by the annotations.
- Merge related genes into broader functional themes.
- Exclude core housekeeping or universal pathways (central metabolism, translation, replication, generic transport).
- Avoid uncertain or speculative traits.
- Exclude any tag if the evidence is weak or only hinted at.
- Express each tag as a short, intuitive phrase (3–6 plain words) describing an integrated capability or adaptation.
- Do not mention specific genes, proteins, or loci.

Output (JSON ONLY):
{"tags": [...]}

If no distinctive features are found, return {"tags": []}.
Return only valid JSON and nothing else.

"""
    return prompt

def parse_tags(response_text):
    """Parse response with strict JSON parsing and robust fallback."""
    text = response_text.strip()

    # Try to find JSON object in the text
    json_match = re.search(r'\{[^}]*"tags"\s*:\s*\[[^\]]*\][^}]*\}', text, re.DOTALL)
    if json_match:
        text = json_match.group(0)
    
    # Attempt JSON parsing
    obj = json.loads(text)
    if isinstance(obj, dict) and 'tags' in obj:
        raw_tags = obj['tags']
        if not isinstance(raw_tags, list):
            print(f"Warning: 'tags' is not a list: {type(raw_tags)}")
            return []
        
        # Clean and deduplicate tags
        tags = []
        seen = set()
        for t in raw_tags:
            if not t:  # Skip empty
                continue
            tag_str = str(t).strip()
            if not tag_str:
                continue
            key = tag_str.lower()
            if key not in seen:
                seen.add(key)
                tags.append(tag_str)
        return tags


## Final function

def collect_tags(file_name, products, organism, strain, sub_strain, output_dir, chunk_size=100):
    print(f'request confirmed: generating tags for {file_name} with {len(products)} products')
    output_log = output_dir + Path(file_name).stem + '_log.txt'
    output_file = output_dir + Path(file_name).stem + '_tags.txt'
    
    with open(output_log, 'w') as f:
        f.write(f'GBFF file: {file_name}\n')
        f.write(f'Total products: {len(products)}\n')
        # f.write(f'products: "{"\n".join(products)}"\n')
    print(f'Log file initialized at {output_log}')

    tags = []
    for idx, chunk in enumerate(chunk_products(products, chunk_size=chunk_size)):
        print(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}]Processing chunk {idx + 1} / {((len(products)-1)//chunk_size)+1} with {len(chunk)} products')
        while True:
            try:
                response = ollama.chat(model=model, messages=[{
                    'role': 'user', 
                    'content': prompt_gen_tags(chunk)
                }])
                
                raw_response = response['message']['content']
                tag = parse_tags(raw_response)
                tags += tag
                with open(output_log, 'a') as f:
                    f.write(f"Raw_response: \n{raw_response}\n")
                    f.write(f"\nParsed tags: \n[{'\n'.join(tag)}]\n")
                    f.write(f"\n\nChunk {idx + 1} processed: {len(tag)}tags collected\n\n")
                    f.write('----------------------------------------\n')
                break
            except Exception as e:
                with open(output_log, 'a') as f:
                    f.write('\n' + str(e) + '\n')
                    f.write('\nRetrying..\n')
        

    # Deduplicate tags case-insensitively while preserving original case
    unique_tags = []
    seen_lower = set()
    for tag in tags:
        tag_lower = tag.lower()
        if tag_lower not in seen_lower:
            seen_lower.add(tag_lower)
            unique_tags.append(tag)
    
    anot_tags = unique_tags

    ser_tags = searching_tags(organism, strain, sub_strain)

    conc_tags = anot_tags + ser_tags


    with open(output_file, 'w') as f:
        f.write("\n".join(conc_tags))
    
    print(f'Processed {file_name}: {len(conc_tags)} tags generated')
    return conc_tags

