import com.oocourse.library2.LibraryBookId;
import com.oocourse.library2.LibraryBookIsbn;

import java.util.HashMap;

public class Reader {
    private final String userId;
    private final HashMap<LibraryBookIsbn, Book> borrowedBooks = new HashMap<>();
    private Book readingBook = null;
    private boolean hasBBook = false;

    public Reader(String userId) {
        this.userId = userId;
    }

    public String getUserId() {
        return userId;
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
        return canHold(isbn);
    }

    public boolean canOrder(LibraryBookIsbn isbn) {
        return canHold(isbn);
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

    public boolean hasBook(LibraryBookIsbn isbn) {
        return borrowedBooks.containsKey(isbn);
    }

    public boolean canRead() {
        return readingBook == null;
    }

    public void read(Book book) {
        readingBook = book;
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
