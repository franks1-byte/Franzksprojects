# Library Management System (Java)

A console app for borrowing and returning books, magazines, and DVDs. Built to show the four OOP pillars in one small program.

## OOP concepts used
| Concept | Where |
|---|---|
| Encapsulation | `Item` keeps `available` and `borrowedBy` private |
| Inheritance | `Book`, `Magazine`, `DVD` extend `Item` |
| Abstraction | `Item` is abstract; `Borrowable` is an interface |
| Polymorphism | `loanDays()`, `type()`, and `matches()` behave differently per item type |

## Run it
```bash
javac -d out src/LibraryApp.java
java -cp out LibraryApp
```
Or open the folder in IntelliJ IDEA and run `LibraryApp.main`.

## Features
- View the full catalog with loan periods and borrow status
- Search by title (and by author for books)
- Borrow and return items, with checks for double-borrowing
