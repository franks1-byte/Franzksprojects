import java.util.ArrayList;
import java.util.List;
import java.util.Scanner;

/**
 * Library Management System
 * Demonstrates: encapsulation, inheritance, abstraction, polymorphism, interfaces.
 */
public class LibraryApp {

    // ===== Interface =====
    interface Borrowable {
        boolean borrow(String memberName);
        void giveBack();
        boolean isAvailable();
    }

    // ===== Abstract base class =====
    static abstract class Item implements Borrowable {
        private static int nextId = 1;
        private final int id;
        private final String title;
        private boolean available = true;
        private String borrowedBy = null;

        Item(String title) {
            this.id = nextId++;
            this.title = title;
        }

        public int getId() { return id; }
        public String getTitle() { return title; }
        public boolean isAvailable() { return available; }

        @Override
        public boolean borrow(String memberName) {
            if (!available) return false;
            available = false;
            borrowedBy = memberName;
            return true;
        }

        @Override
        public void giveBack() {
            available = true;
            borrowedBy = null;
        }

        /** Each subclass decides how many days it can be borrowed (polymorphism). */
        public abstract int loanDays();
        public abstract String type();

        /** Subclasses can widen what a search matches (e.g. Book also checks the author). */
        public boolean matches(String keyword) {
            return title.toLowerCase().contains(keyword.toLowerCase());
        }

        @Override
        public String toString() {
            String status = available ? "Available" : "Borrowed by " + borrowedBy;
            return String.format("#%-3d %-9s %-32s %2d days  %s",
                    id, type(), title, loanDays(), status);
        }
    }

    // ===== Subclasses =====
    static class Book extends Item {
        private final String author;
        Book(String title, String author) { super(title); this.author = author; }
        public int loanDays() { return 14; }
        public String type() { return "Book"; }
        @Override public boolean matches(String keyword) {
            return super.matches(keyword) || author.toLowerCase().contains(keyword.toLowerCase());
        }
        @Override public String toString() { return super.toString() + "  (by " + author + ")"; }
    }

    static class Magazine extends Item {
        Magazine(String title) { super(title); }
        public int loanDays() { return 7; }
        public String type() { return "Magazine"; }
    }

    static class DVD extends Item {
        private final int minutes;
        DVD(String title, int minutes) { super(title); this.minutes = minutes; }
        public int loanDays() { return 3; }
        public String type() { return "DVD"; }
        @Override public String toString() { return super.toString() + "  (" + minutes + " min)"; }
    }

    // ===== Library =====
    static class Library {
        private final List<Item> items = new ArrayList<>();

        void add(Item item) { items.add(item); }

        Item find(int id) {
            for (Item i : items) if (i.getId() == id) return i;
            return null;
        }

        List<Item> search(String keyword) {
            List<Item> results = new ArrayList<>();
            for (Item i : items)
                if (i.matches(keyword.trim())) results.add(i);
            return results;
        }

        void printAll() {
            System.out.println("\n----------------------------------- CATALOG -----------------------------------");
            for (Item i : items) System.out.println(i);
            long out = items.stream().filter(i -> !i.isAvailable()).count();
            System.out.println("Total: " + items.size() + " items, " + out + " borrowed");
        }
    }

    // ===== Main menu =====
    public static void main(String[] args) {
        Library lib = new Library();
        lib.add(new Book("Noli Me Tangere", "Jose Rizal"));
        lib.add(new Book("El Filibusterismo", "Jose Rizal"));
        lib.add(new Book("Clean Code", "Robert C. Martin"));
        lib.add(new Book("Head First Java", "Kathy Sierra"));
        lib.add(new Magazine("National Geographic - October"));
        lib.add(new Magazine("Wired - Tech Special"));
        lib.add(new DVD("Cosmos: A Spacetime Odyssey", 540));
        lib.add(new DVD("The Social Network", 120));

        Scanner in = new Scanner(System.in);
        while (true) {
            System.out.println("\n=== LIBRARY SYSTEM ===");
            System.out.println("1) View catalog  2) Search  3) Borrow  4) Return  0) Exit");
            System.out.print("> ");
            if (!in.hasNextLine()) break;
            String choice = in.nextLine().trim();

            switch (choice) {
                case "1" -> lib.printAll();
                case "2" -> {
                    System.out.print("Keyword: ");
                    List<Item> found = lib.search(in.nextLine());
                    if (found.isEmpty()) System.out.println("No matches.");
                    else found.forEach(System.out::println);
                }
                case "3" -> {
                    Item item = askForItem(in, lib);
                    if (item == null) break;
                    System.out.print("Your name: ");
                    String name = in.nextLine().trim();
                    if (item.borrow(name))
                        System.out.println("Borrowed! Please return within " + item.loanDays() + " days.");
                    else System.out.println("Sorry, that item is already borrowed.");
                }
                case "4" -> {
                    Item item = askForItem(in, lib);
                    if (item == null) break;
                    if (item.isAvailable()) System.out.println("That item wasn't borrowed.");
                    else { item.giveBack(); System.out.println("Returned. Thank you!"); }
                }
                case "0" -> { System.out.println("Goodbye!"); return; }
                default -> System.out.println("Invalid choice.");
            }
        }
    }

    private static Item askForItem(Scanner in, Library lib) {
        System.out.print("Item ID: ");
        try {
            Item item = lib.find(Integer.parseInt(in.nextLine().trim()));
            if (item == null) System.out.println("No item with that ID.");
            return item;
        } catch (NumberFormatException e) {
            System.out.println("Please enter a number.");
            return null;
        }
    }
}
