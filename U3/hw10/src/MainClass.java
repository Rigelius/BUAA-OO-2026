import com.oocourse.spec2.main.Runner;

public class MainClass {
    public static void main(String[] args) throws Exception {
        Runner runner = new Runner(User.class, Network.class, Video.class);
        runner.run();
    }
}
