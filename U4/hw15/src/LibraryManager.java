import com.oocourse.library3.LibraryBookId;
import com.oocourse.library3.LibraryBookIsbn;
import com.oocourse.library3.LibraryBookState;
import com.oocourse.library3.LibraryIO;
import com.oocourse.library3.LibraryMoveInfo;
import com.oocourse.library3.LibraryReqCmd;
import com.oocourse.library3.LibraryQcsCmd;
import com.oocourse.library3.LibraryTrace;
import com.oocourse.library3.annotation.Trigger;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.Map;

public class LibraryManager {
    private final Bookshelf bookshelf;
    private final TreasuredBookshelf treasuredBookshelf;
    private final BorrowAndReturnOffice borrowAndReturnOffice;
    private final AppointmentOffice appointmentOffice;
    private final ReadingRoom readingRoom;
    private final RatingOffice ratingOffice;
    private final HashMap<String, Reader> user = new HashMap<>();
    private final HashMap<LibraryBookId, String> readingBookOwners = new HashMap<>();

    public LibraryManager(Map<LibraryBookIsbn, Integer> bookList) {
        this.treasuredBookshelf = new TreasuredBookshelf(bookList);
        this.bookshelf = new Bookshelf(bookList, treasuredBookshelf);
        this.borrowAndReturnOffice = new BorrowAndReturnOffice();
        this.appointmentOffice = new AppointmentOffice();
        this.readingRoom = new ReadingRoom();
        this.ratingOffice = new RatingOffice();
    }

    @Trigger(from = "AppointmentOffice", to = { "Bookshelf", "TreasuredBookshelf" })
    @Trigger(from = "BorrowAndReturnOffice", to = { "Bookshelf", "TreasuredBookshelf" })
    @Trigger(from = "ReadingRoom", to = { "Bookshelf", "TreasuredBookshelf" })
    @Trigger(from = "Bookshelf", to = { "AppointmentOffice", "TreasuredBookshelf" })
    @Trigger(from = "TreasuredBookshelf", to = { "AppointmentOffice", "Bookshelf" })
    public void open(LocalDate date) {
        updateAllUsersOverdue(date, false);
        ArrayList<LibraryMoveInfo> moves = new ArrayList<>();
        moves.addAll(arrangeExpiredAppointmentBooks(date, true));
        moves.addAll(arrangeReadingRoom(date, true));
        moves.addAll(arrangeBorrowAndReturnOffice(date, true));
        moves.addAll(arrangeBookshelves(date));
        moves.addAll(arrangePendingOrders(date, true));
        LibraryIO.PRINTER.move(date, moves);
    }

    @Trigger(from = "AppointmentOffice", to = "Bookshelf")
    @Trigger(from = "ReadingRoom", to = "Bookshelf")
    @Trigger(from = "Bookshelf", to = "AppointmentOffice")
    @Trigger(from = "TreasuredBookshelf", to = "AppointmentOffice")
    public void close(LocalDate date) {
        ArrayList<LibraryMoveInfo> moves = new ArrayList<>();
        moves.addAll(arrangeExpiredAppointmentBooks(date, false));
        moves.addAll(arrangeReadingRoom(date, false));
        moves.addAll(arrangePendingOrders(date, false));
        updateAllUsersOverdue(date, true);
        LibraryIO.PRINTER.move(date, moves);
    }

    public void serve(LibraryReqCmd cmd) {
        switch (cmd.getType()) {
            case QUERIED:
                query(cmd);
                break;
            case BORROWED:
                borrowBook(cmd);
                break;
            case RETURNED:
                returnBook(cmd);
                break;
            case ORDERED:
                orderBook(cmd);
                break;
            case PICKED:
                pickBook(cmd);
                break;
            case READ:
                readBook(cmd);
                break;
            case RESTORED:
                restoreBook(cmd);
                break;
            case GRADED:
                gradeBook(cmd);
                break;
            case RENEWED:
                renewBook(cmd);
                break;
            default:
                break;
        }
    }

    public void queryCreditScore(LibraryQcsCmd cmd) {
        Reader reader = getReader(cmd.getStudentId());
        LibraryIO.PRINTER.info(cmd, reader.getCreditScore());
    }

    private void updateAllUsersOverdue(LocalDate date, boolean isClose) {
        for (Reader reader : user.values()) {
            reader.updateOverduePenalties(date, isClose);
        }
    }

    @Trigger(from = "Bookshelf", to = "User")
    @Trigger(from = "TreasuredBookshelf", to = "User")
    public void borrowBook(LibraryReqCmd cmd) {
        LibraryBookIsbn isbn = cmd.getBookIsbn();
        Reader reader = getReader(cmd.getStudentId());
        if (reader.canBorrow(isbn) && bookshelf.hasBook(isbn)) {
            Book book = bookshelf.takeBook(isbn);
            book.setDueDate(cmd.getDate().plusDays(isbn.isTypeB() ? 15 : 30));
            move(book, LibraryBookState.USER, cmd.getDate());
            reader.borrow(book);
            LibraryIO.PRINTER.accept(cmd, book.getBookCopyId());
        } else {
            LibraryIO.PRINTER.reject(cmd);
        }
    }

    @Trigger(from = "User", to = "BorrowAndReturnOffice")
    public void returnBook(LibraryReqCmd cmd) {
        Reader reader = getReader(cmd.getStudentId());
        Book book = reader.returnBook(cmd.getBookId());
        if (book == null) {
            LibraryIO.PRINTER.reject(cmd);
            return;
        }
        boolean isOverdue = cmd.getDate().isAfter(book.getDueDate());
        if (!isOverdue) {
            reader.addCredit(10);
        }
        move(book, LibraryBookState.BORROW_RETURN_OFFICE, cmd.getDate());
        borrowAndReturnOffice.acceptReturnedBook(book);
        LibraryIO.PRINTER.accept(cmd, isOverdue ? "overdue" : "not overdue");
    }

    public void orderBook(LibraryReqCmd cmd) {
        Reader reader = getReader(cmd.getStudentId());
        LibraryBookIsbn isbn = cmd.getBookIsbn();
        if (reader.canOrder(isbn) && !appointmentOffice.hasOrdered(cmd.getStudentId())) {
            appointmentOffice.orderBook(cmd.getStudentId(), isbn);
            LibraryIO.PRINTER.accept(cmd);
        } else {
            LibraryIO.PRINTER.reject(cmd);
        }
    }

    @Trigger(from = "AppointmentOffice", to = "User")
    public void pickBook(LibraryReqCmd cmd) {
        Reader reader = getReader(cmd.getStudentId());
        LibraryBookIsbn isbn = cmd.getBookIsbn();
        if (reader.canPick(isbn) && appointmentOffice.hasReservedBook(cmd.getStudentId(), isbn)) {
            Book book = appointmentOffice.pickBook(cmd.getStudentId(), isbn);
            book.setDueDate(cmd.getDate().plusDays(isbn.isTypeB() ? 15 : 30));
            move(book, LibraryBookState.USER, cmd.getDate());
            reader.borrow(book);
            LibraryIO.PRINTER.accept(cmd, book.getBookCopyId());
        } else {
            LibraryIO.PRINTER.reject(cmd);
        }
    }

    @Trigger(from = "Bookshelf", to = "ReadingRoom")
    @Trigger(from = "TreasuredBookshelf", to = "ReadingRoom")
    public void readBook(LibraryReqCmd cmd) {
        LibraryBookIsbn isbn = cmd.getBookIsbn();
        Reader reader = getReader(cmd.getStudentId());
        if (reader.canRead(isbn) && bookshelf.hasBook(isbn)) {
            Book book = bookshelf.takeBook(isbn);
            move(book, LibraryBookState.READING_ROOM, cmd.getDate());
            reader.read(book);
            readingRoom.acceptReadBook(book);
            readingBookOwners.put(book.getBookCopyId(), cmd.getStudentId());
            LibraryIO.PRINTER.accept(cmd, book.getBookCopyId());
        } else {
            LibraryIO.PRINTER.reject(cmd);
        }
    }

    @Trigger(from = "ReadingRoom", to = "BorrowAndReturnOffice")
    public void restoreBook(LibraryReqCmd cmd) {
        Reader reader = getReader(cmd.getStudentId());
        Book book = reader.restoreBook(cmd.getBookId());
        if (book == null) {
            LibraryIO.PRINTER.reject(cmd);
            return;
        }
        reader.addCredit(10);
        readingRoom.restoreBook(cmd.getBookId());
        readingBookOwners.remove(cmd.getBookId());
        move(book, LibraryBookState.BORROW_RETURN_OFFICE, cmd.getDate());
        borrowAndReturnOffice.restore(book);
        LibraryIO.PRINTER.accept(cmd);
    }

    public void gradeBook(LibraryReqCmd cmd) {
        ratingOffice.gradeBook(cmd.getBookIsbn(), cmd.getScore());
        LibraryIO.PRINTER.accept(cmd);
    }

    public void renewBook(LibraryReqCmd cmd) {
        Reader reader = getReader(cmd.getStudentId());
        Book book = reader.getBorrowedBook(cmd.getBookId());
        if (book != null) {
            boolean isOverdue = cmd.getDate().isAfter(book.getDueDate());
            if (!isOverdue) {
                book.setDueDate(book.getDueDate().plusDays(7));
                LibraryIO.PRINTER.accept(cmd);
                return;
            }
        }
        LibraryIO.PRINTER.reject(cmd);
    }

    public void query(LibraryReqCmd cmd) {
        ArrayList<LibraryTrace> traces = bookshelf.query(cmd.getBookId());
        LibraryIO.PRINTER.info(cmd.getDate(), cmd.getBookId(), traces);
    }

    public ArrayList<LibraryMoveInfo> arrangeBorrowAndReturnOffice(
            LocalDate date, boolean beforeOpen) {
        ArrayList<LibraryMoveInfo> moves = new ArrayList<>();
        for (Book book : borrowAndReturnOffice.drainBooks()) {
            LibraryBookState from = book.getState();
            LibraryBookState to = beforeOpen ? getShelfState(book.getIsbn())
                    : LibraryBookState.BOOKSHELF;
            move(book, to, date);
            bookshelf.putBook(book, to);
            moves.add(new LibraryMoveInfo(book.getBookCopyId(), from, to));
        }
        return moves;
    }

    public ArrayList<LibraryMoveInfo> arrange(LocalDate date) {
        return arrangeBorrowAndReturnOffice(date, true);
    }

    public ArrayList<LibraryMoveInfo> arrangeReadingRoom(LocalDate date, boolean beforeOpen) {
        ArrayList<LibraryMoveInfo> moves = new ArrayList<>();
        for (Book book : readingRoom.drainBooks()) {
            final LibraryBookState from = book.getState();
            String userId = readingBookOwners.remove(book.getBookCopyId());
            if (userId != null) {
                getReader(userId).clearReadingBook();
                getReader(userId).subCredit(10);
            }
            LibraryBookState to = beforeOpen ? getShelfState(book.getIsbn())
                    : LibraryBookState.BOOKSHELF;
            move(book, to, date);
            bookshelf.putBook(book, to);
            moves.add(new LibraryMoveInfo(book.getBookCopyId(), from, to));
        }
        return moves;
    }

    public ArrayList<LibraryMoveInfo> arrangeExpiredAppointmentBooks(
            LocalDate date, boolean beforeOpen) {
        ArrayList<LibraryMoveInfo> moves = new ArrayList<>();
        HashMap<String, Book> expiredBooks = appointmentOffice.getExpiredBooks(date, beforeOpen);
        for (Map.Entry<String, Book> entry : expiredBooks.entrySet()) {
            String userId = entry.getKey();
            Book book = entry.getValue();
            getReader(userId).subCredit(15);
            LibraryBookState from = book.getState();
            LibraryBookState to = beforeOpen ? getShelfState(book.getIsbn())
                    : LibraryBookState.BOOKSHELF;
            move(book, to, date);
            bookshelf.putBook(book, to);
            moves.add(new LibraryMoveInfo(book.getBookCopyId(), from, to));
        }
        return moves;
    }

    public ArrayList<LibraryMoveInfo> arrangeBookshelves(LocalDate date) {
        ArrayList<LibraryMoveInfo> moves = new ArrayList<>();
        HashSet<LibraryBookIsbn> treasuredIsbns = ratingOffice.getTreasuredIsbns();
        for (Book book : bookshelf.arrangeTreasuredBooks(treasuredIsbns)) {
            LibraryBookState from = book.getState();
            move(book, LibraryBookState.TREASURED_BOOKSHELF, date);
            moves.add(new LibraryMoveInfo(
                    book.getBookCopyId(), from, LibraryBookState.TREASURED_BOOKSHELF));
        }
        for (Book book : bookshelf.arrangeNormalBooks(treasuredIsbns)) {
            LibraryBookState from = book.getState();
            move(book, LibraryBookState.BOOKSHELF, date);
            moves.add(new LibraryMoveInfo(
                    book.getBookCopyId(), from, LibraryBookState.BOOKSHELF));
        }
        return moves;
    }

    public ArrayList<LibraryMoveInfo> arrangePendingOrders(LocalDate date, boolean beforeOpen) {
        ArrayList<LibraryMoveInfo> moves = new ArrayList<>();
        HashMap<String, LibraryBookIsbn> pendingOrders = appointmentOffice.getPendingOrders();
        Iterator<Map.Entry<String, LibraryBookIsbn>> iterator = pendingOrders.entrySet().iterator();
        while (iterator.hasNext()) {
            Map.Entry<String, LibraryBookIsbn> entry = iterator.next();
            if (!bookshelf.hasBook(entry.getValue())) {
                continue;
            }
            Book book = bookshelf.takeBook(entry.getValue());
            LibraryBookState from = book.getState();
            move(book, LibraryBookState.APPOINTMENT_OFFICE, date);
            appointmentOffice.keepBook(entry.getKey(), book, date, beforeOpen);
            moves.add(new LibraryMoveInfo(
                    book.getBookCopyId(), from, LibraryBookState.APPOINTMENT_OFFICE,
                    entry.getKey()));
            iterator.remove();
        }
        return moves;
    }

    public void move(Book book, LibraryBookState to, LocalDate date) {
        book.moveTo(to, date);
    }

    private LibraryBookState getShelfState(LibraryBookIsbn isbn) {
        return ratingOffice.isTreasuredBook(isbn)
                ? LibraryBookState.TREASURED_BOOKSHELF : LibraryBookState.BOOKSHELF;
    }

    private Reader getReader(String userId) {
        return user.computeIfAbsent(userId, Reader::new);
    }

}

