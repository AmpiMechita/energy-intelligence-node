# ⚡ Energy Intelligence Node (EIN)

**Open-Source AI to Audit Climate Tech Claims and Fight Greenwashing.**

The transition to renewable energy is being slowed down by two things: physical engineering bottlenecks, and corporate greenwashing. EIN is an autonomous, open-source intelligence pipeline that ingests scientific papers (ArXiv), patents (USPTO), and technical press, extracts physical claims (e.g., "500 Wh/kg density", "99% efficiency"), and uses LLMs to detect contradictions, hype, and scaling failures.

## 🌍 Why This Matters (Energy Justice)

Global South governments and marginalized (MAPA) communities often lack the technical capacity to audit whether a multi-million dollar green technology (e.g., solid-state batteries, green hydrogen) actually works or if it's venture capital marketing. EIN levels the playing field by providing institutional-grade technology intelligence that can be run locally on a standard laptop, without relying on expensive proprietary APIs.

## ⚙️ How It Works

1. **Ingestion:** Automated scraping of ArXiv (energy physics) and technical RSS feeds.
2. **Extraction:** Regex-based extraction of physical metrics (Wh/kg, %, $/kWh, cycles).
3. **Contradiction Engine:** An LLM agent cross-references claims to expose exaggerated metrics or hidden physical limitations (e.g., detecting that a battery's lab efficiency drops 40% at module level).
4. **Output:** Structured intelligence reports generated in seconds, not hours.

## 🤝 Contributing

We are actively seeking collaborators, especially data scientists, energy researchers, and open-source advocates from the Global South. Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
