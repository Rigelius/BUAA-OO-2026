import com.oocourse.library2.LibraryBookId;
import com.oocourse.library2.LibraryBookIsbn;
import com.oocourse.library2.LibraryBookState;
import com.oocourse.library2.LibraryTrace;

import java.time.LocalDate;
import java.util.ArrayList;

public class Book {
    private final LibraryBookId bookCopyId;
    private final LibraryBookIsbn isbn;
    private final LibraryBookIsbn.Type bookCategory;
    private LibraryBookState state;
    private final ArrayList<LibraryTrace> movingTrace = new ArrayList<>();

    public Book(LibraryBookId bookCopyId) {
        this.bookCopyId = bookCopyId;
        this.isbn = bookCopyId.getBookIsbn();
        this.bookCategory = bookCopyId.getType();
        this.state = LibraryBookState.BOOKSHELF;
    }

    public LibraryBookId getBookCopyId() {
        return bookCopyId;
    }

    public LibraryBookIsbn getIsbn() {
        return isbn;
    }

    public LibraryBookIsbn.Type getBookCategory() {
        return bookCategory;
    }

    public LibraryBookState getState() {
        return state;
    }

    public void moveTo(LibraryBookState to, LocalDate date) {
        movingTrace.add(new LibraryTrace(date, state, to));
        state = to;
    }

    public ArrayList<LibraryTrace> queryMovingTrace() {
        return movingTrace;
    }
}
