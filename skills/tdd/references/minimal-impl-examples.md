# Minimal Implementation: Domain-Specific Patterns

The principle: implement exactly what the test requires, nothing more. Examples are Python; translate the shape to your stack.

## Math Functions: Direct Formula

```python
# Test: assert calculate_discount(100, 10) == 90

def calculate_discount(price, discount_percent):
    return price * (1 - discount_percent / 100)
```

```python
# NOT minimal (adds validation not yet tested)
def calculate_discount(price, discount_percent):
    if price < 0:
        raise ValueError("Price must be >= 0")
    return price * (1 - discount_percent / 100)
```

Add the validation when its test arrives.

## Validation Functions: Simple Boolean Check

```python
# Test: assert validator.validate_email("x@y.com") == True

def validate_email(self, email):
    return '@' in email
```

```python
# NOT minimal (adds regex not yet tested)
def validate_email(self, email):
    import re
    return bool(re.match(r'^[^@]+@[^@]+\.[^@]+$', email))
```

Add the regex when the RFC-compliance test arrives.

## Parsing / String Processing: Iterate As Needed

```python
# Test: assert parse("a,b,c") == ["a", "b", "c"]

# Minimal (correct) — iteration is necessary to pass this test
def parse(self, line):
    return line.split(',')
```

```python
# Later test: assert parse("a,b\nc,d") handles newlines
# Minimal (correct) at this point
def parse(self, data):
    return [line.split(',') for line in data.split('\n')]
```

Each feature gets its own test and minimal implementation.

## Classes: Extract Helpers Only On Duplication

```python
# Test 1: assert validator.validate_email() == True
class UserValidator:
    def validate_email(self, email):
        return '@' in email
```

```python
# Test 2: assert validator.validate_password() == True
# Minimal (correct) — no helper extracted yet (no duplicated logic)
class UserValidator:
    def validate_email(self, email):
        return '@' in email
    def validate_password(self, pwd):
        return '#' in pwd  # requires a symbol — same "contains required char" shape
```

```python
# Test 3: assert combined validation — both methods now check "contains a required char"
# NOW extract (correct): _contains_required_character(email, '@') and _contains_required_character(pwd, '#')
def _contains_required_character(self, text, char):
    return char in text
```

Extract only when actual duplication appears — not "just in case".
