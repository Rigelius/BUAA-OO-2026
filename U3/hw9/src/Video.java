import com.oocourse.spec1.main.VideoInterface;

public class Video implements VideoInterface {
    private final int id;
    private final int uploaderId;

    public Video(int id, int uploaderId) {
        this.id = id;
        this.uploaderId = uploaderId;
    }

    @Override
    public int getId() {
        return id;
    }

    @Override
    public int getUploaderId() {
        return uploaderId;
    }

    @Override
    public boolean equals(Object obj) {
        if (!(obj instanceof VideoInterface)) {
            return false;
        }
        return ((VideoInterface) obj).getId() == id;
    }
}
