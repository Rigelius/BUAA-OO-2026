import com.oocourse.library3.LibraryBookId;
import com.oocourse.library3.LibraryBookIsbn;

import java.time.LocalDate;
import java.util.HashMap;

public class Reader {
    private final String userId;
    private final HashMap<LibraryBookIsbn, Book> borrowedBooks = new HashMap<>();
    private Book readingBook = null;
    private boolean hasBBook = false;
    private int creditScore = 100;

    public Reader(String userId) {
        this.userId = userId;
    }

    public String getUserId() {
        return userId;
    }

    public int getCreditScore() {
        return creditScore;
    }

    public void addCredit(int delta) {
        creditScore = Math.min(180, creditScore + delta);
    }

    public void subCredit(int delta) {
        creditScore = Math.max(0, creditScore - delta);
    }

    public boolean checkBorrowLimit(LibraryBookIsbn isbn) {
        if (isbn.isTypeA()) {
            return false;
        } else if (isbn.isTypeB()) {
            return !hasBBook;
        } else {
            return !hasBook(isbn);
        }
    }

    public boolean canHold(LibraryBookIsbn isbn) {
        return checkBorrowLimit(isbn);
    }

    public boolean canBorrow(LibraryBookIsbn isbn) {
        return canHold(isbn) && creditScore > 80;
    }

    public boolean canOrder(LibraryBookIsbn isbn) {
        return canHold(isbn) && creditScore > 80;
    }

    public boolean canPick(LibraryBookIsbn isbn) {
        return canHold(isbn);
    }

    public void borrow(Book book) {
        if (book.getIsbn().isTypeB()) {
            hasBBook = true;
        }
        borrowedBooks.put(book.getIsbn(), book);
    }

    public Book returnBook(LibraryBookId bookId) {
        LibraryBookIsbn isbn = bookId.getBookIsbn();
        Book book = borrowedBooks.get(isbn);
        if (book == null || !book.getBookCopyId().equals(bookId)) {
            return null;
        }
        if (isbn.isTypeB()) {
            hasBBook = false;
        }
        return borrowedBooks.remove(isbn);
    }

    public Book getBorrowedBook(LibraryBookId bookId) {
        LibraryBookIsbn isbn = bookId.getBookIsbn();
        Book book = borrowedBooks.get(isbn);
        if (book != null && book.getBookCopyId().equals(bookId)) {
            return book;
        }
        return null;
    }

    public Iterable<Book> getBorrowedBooks() {
        return borrowedBooks.values();
    }

    public boolean hasBook(LibraryBookIsbn isbn) {
        return borrowedBooks.containsKey(isbn);
    }

    public boolean canRead(LibraryBookIsbn isbn) {
        if (readingBook != null) { return false; }
        if (isbn.isTypeA()) { return creditScore > 40; }
        return creditScore > 0;
    }

    public void read(Book book) {
        readingBook = book;
    }

    public void updateOverduePenalties(LocalDate date, boolean isClose) {
        for (Book book : borrowedBooks.values()) {
            if (!book.isOverduePenaltyApplied()) {
                boolean shouldApply = isClose ? !date.isBefore(book.getDueDate())
                        : date.isAfter(book.getDueDate());
                if (shouldApply) {
                    subCredit(15);
                    book.setOverduePenaltyApplied(true);
                }
            }
        }
    }

    public Book restoreBook(LibraryBookId bookId) {
        if (readingBook == null || !readingBook.getBookCopyId().equals(bookId)) {
            return null;
        }
        Book book = readingBook;
        readingBook = null;
        return book;
    }

    public void clearReadingBook() {
        readingBook = null;
    }
}
