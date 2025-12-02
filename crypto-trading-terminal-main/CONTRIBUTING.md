# Contributing to Crypto Trading Terminal

Thank you for your interest in contributing to the Crypto Trading Terminal! This document provides guidelines and information for contributors.

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- Git
- Basic understanding of trading concepts
- Familiarity with Dash/Plotly (helpful but not required)

### Development Setup

1. **Fork the repository**
   ```bash
   git clone https://github.com/yourusername/crypto-trading-terminal.git
   cd crypto-trading-terminal
   ```

2. **Set up development environment**
   ```bash
   ./setup.sh
   source venv/bin/activate
   ```

3. **Install development dependencies**
   ```bash
   pip install -r requirements-dev.txt
   ```

## 📝 How to Contribute

### Types of Contributions

We welcome several types of contributions:

- **Bug Reports**: Help us identify and fix issues
- **Feature Requests**: Suggest new functionality
- **Code Contributions**: Implement new features or fix bugs
- **Documentation**: Improve guides, comments, and README
- **Testing**: Add tests or help with quality assurance

### Bug Reports

When reporting bugs, please include:

- **Clear Description**: What happened vs. what you expected
- **Steps to Reproduce**: Detailed steps to recreate the issue
- **Environment**: Python version, OS, browser, etc.
- **Logs**: Any error messages or console output
- **Screenshots**: If applicable, visual evidence of the issue

### Feature Requests

For new features, please:

- **Check Existing Issues**: Ensure the feature isn't already requested
- **Provide Context**: Explain the use case and benefits
- **Consider Implementation**: Basic technical approach if you have ideas
- **Tag Appropriately**: Use the "enhancement" label

### Code Contributions

#### Development Workflow

1. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**
   - Follow the coding standards below
   - Add tests for new functionality
   - Update documentation as needed

3. **Test Your Changes**
   ```bash
   python -m pytest tests/
   python terminal/app.py  # Test manually
   ```

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: add new signal filtering feature"
   ```

5. **Push and Create Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```

#### Coding Standards

**Python Style Guide:**
- Follow PEP 8
- Use type hints where possible
- Maximum line length: 100 characters
- Use descriptive variable names

**Code Organization:**
```python
# Imports (standard library, third-party, local)
import os
import sys
from typing import List, Dict

import pandas as pd
import plotly.graph_objects as go

from .config import config
from .data.hyperliquid_api import api_client
```

**Documentation:**
```python
def calculate_rsi(prices: List[float], period: int = 14) -> float:
    """
    Calculate Relative Strength Index (RSI).
    
    Args:
        prices: List of closing prices
        period: RSI calculation period (default: 14)
    
    Returns:
        RSI value between 0 and 100
    
    Raises:
        ValueError: If prices list is empty or period is invalid
    """
    # Implementation here
```

#### Testing Requirements

- **Unit Tests**: Test individual functions and classes
- **Integration Tests**: Test component interactions
- **Manual Testing**: Verify UI functionality
- **Performance Tests**: Ensure no significant slowdowns

Example test structure:
```python
# tests/test_signal_detection.py
import pytest
from terminal.trading.signal_trader import SignalTrader

def test_rsi_calculation():
    """Test RSI calculation with known values."""
    prices = [100, 102, 101, 103, 105, 104, 106, 108, 107, 109]
    trader = SignalTrader()
    rsi = trader.calculate_rsi(prices, 14)
    assert 0 <= rsi <= 100
```

## 🏗️ Project Structure

Understanding the codebase:

```
terminal/
├── app.py                    # Main Dash application
├── config.py                 # Configuration settings
├── components/               # UI components
│   ├── analytics_dashboard.py
│   ├── spaghetti.py
│   ├── rsi_plotter.py
│   └── alerts.py
├── data/                     # Data processing
│   ├── analytics_db.py
│   ├── hyperliquid_api.py
│   └── data_processor.py
├── trading/                  # Trading logic
│   ├── signal_trader.py
│   └── position_manager.py
└── tests/                    # Test files
    ├── test_signal_detection.py
    └── test_api_integration.py
```

## 🔧 Development Guidelines

### Key Components

**Signal Detection (`trading/signal_trader.py`):**
- Implements the 4-star signal system
- Handles RSI, VAL, and RVWAP calculations
- Manages trade execution logic

**Analytics (`data/analytics_db.py`):**
- SQLite database operations
- Signal and trade data management
- Performance tracking

**UI Components (`components/`):**
- Dash/Plotly-based interface
- Real-time data visualization
- Interactive charts and tables

### Common Tasks

**Adding a New Signal Criterion:**
1. Update `signal_trader.py` with new calculation
2. Add to 4-star signal logic
3. Update analytics database schema
4. Add visualization if needed

**Improving Performance:**
1. Profile the code to identify bottlenecks
2. Optimize database queries
3. Implement caching where appropriate
4. Update requirements if needed

**Enhancing UI:**
1. Follow existing Matrix theme styling
2. Ensure responsive design
3. Test on different screen sizes
4. Maintain accessibility standards

## 🧪 Testing

### Running Tests

```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest tests/test_signal_detection.py

# Run with coverage
python -m pytest --cov=terminal

# Run with verbose output
python -m pytest -v
```

### Test Categories

- **Unit Tests**: Individual function testing
- **Integration Tests**: Component interaction testing
- **UI Tests**: Manual interface testing
- **Performance Tests**: Speed and memory usage

### Test Data

Use testnet data and mock APIs for testing:
- Never use real trading data in tests
- Mock external API calls
- Use consistent test datasets

## 📋 Pull Request Process

### Before Submitting

1. **Test Thoroughly**
   - Run all existing tests
   - Test your changes manually
   - Check for regressions

2. **Update Documentation**
   - Update README if needed
   - Add code comments
   - Update API documentation

3. **Check Code Quality**
   - Follow style guidelines
   - Remove debug prints
   - Optimize performance

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests pass locally
- [ ] Manual testing completed
- [ ] No regressions found

## Screenshots (if applicable)
Add screenshots for UI changes

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Tests added/updated
```

### Review Process

1. **Automated Checks**: CI/CD pipeline runs tests
2. **Code Review**: Maintainers review code quality
3. **Testing**: Manual testing by maintainers
4. **Approval**: Maintainer approval required
5. **Merge**: Changes integrated into main branch

## 🐛 Issue Templates

### Bug Report Template

```markdown
**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior

**Expected behavior**
What you expected to happen

**Screenshots**
If applicable, add screenshots

**Environment**
- OS: [e.g., macOS 13.0]
- Python: [e.g., 3.11.0]
- Browser: [e.g., Chrome 118]

**Additional context**
Any other relevant information
```

### Feature Request Template

```markdown
**Is your feature request related to a problem?**
A clear description of what the problem is.

**Describe the solution you'd like**
A clear description of what you want to happen.

**Describe alternatives you've considered**
Alternative solutions or features you've considered.

**Additional context**
Any other context about the feature request.
```

## 🤝 Community Guidelines

### Code of Conduct

- **Be Respectful**: Treat everyone with respect
- **Be Constructive**: Provide helpful feedback
- **Be Patient**: Remember that contributors are volunteers
- **Be Professional**: Keep discussions focused and productive

### Communication

- **GitHub Issues**: For bug reports and feature requests
- **Pull Requests**: For code contributions and discussions
- **Discussions**: For general questions and ideas

## 📚 Resources

### Documentation
- [Dash Documentation](https://dash.plotly.com/)
- [Plotly Python Documentation](https://plotly.com/python/)
- [Hyperliquid API Documentation](https://hyperliquid.gitbook.io/hyperliquid/)

### Learning Materials
- Python trading tutorials
- Dash/Plotly examples
- Cryptocurrency trading concepts
- Risk management principles

## 🏆 Recognition

Contributors will be recognized in:
- CONTRIBUTORS.md file
- Release notes
- Community acknowledgments

## 📞 Getting Help

If you need help:
1. Check existing documentation
2. Search GitHub issues
3. Ask questions in discussions
4. Contact maintainers directly

---

Thank you for contributing to the Crypto Trading Terminal! 🚀
