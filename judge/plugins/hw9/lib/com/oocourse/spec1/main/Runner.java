package com.oocourse.spec1.main;

import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationTargetException;
import java.util.List;
import java.util.Scanner;

import com.oocourse.spec1.exceptions.*;

public class Runner {
    
    private String[] commands;
    private NetworkInterface network;

    private final Constructor<? extends UserInterface> userConstructor;
    private final Constructor<? extends NetworkInterface> networkConstructor;
    private final Constructor<? extends VideoInterface> videoConstructor;
    
    private final Scanner scanner;

    public Runner(Class<? extends UserInterface> userClass,
                  Class<? extends NetworkInterface> networkClass,
                  Class<? extends VideoInterface> videoClass)
            throws NoSuchMethodException, SecurityException {

        userConstructor = userClass.getConstructor(
                int.class, String.class, int.class);

        networkConstructor = networkClass.getConstructor();

        videoConstructor = videoClass.getConstructor(int.class, int.class);
        scanner = new Scanner(System.in);
    }

    private String getCurrentCommandString() {
        if (commands == null) return "";
        return String.join(" ", commands);
    }
    
    public void run()
            throws InstantiationException, IllegalAccessException,
            IllegalArgumentException, InvocationTargetException {

        this.network = this.networkConstructor.newInstance();
        while (scanner.hasNextLine()) {
            String line = scanner.nextLine().trim();
            if (line.isEmpty()) continue;
            
            commands = line.split("\\s+");
            String cmd = commands[0];
            try {
                switch (cmd) {
                    case "add_user":
                        addUser();
                        break;
                    case "upload_video":
                        uploadVideo();
                        break;
                    case "follow_user":
                        followUser();
                        break;
                    case "unfollow_user":
                        unfollowUser();
                        break;
                    case "watch_video":
                        watchVideo();
                        break;
                    case "query_received_unwatched_videos":
                        queryReceivedUnwatchedVideos();
                        break;
                    case "query_up_followers_age_ratio":
                        queryUpFollowersAgeRatio();
                        break;
                    case "query_mutual_following_sum":
                        queryMutualFollowingSum();
                        break;
                    case "query_shortest_path":
                        queryShortestPath();
                        break;
                    case "end":
                        return ;
                    default:
                        break;
                }
            } catch (Exception e) {
                if (e instanceof InvocationTargetException) {
                    Throwable target = ((InvocationTargetException) e).getTargetException();
                    if (target instanceof MyException) {
                        ((MyException) target).print();
                        if (target instanceof Exception) {
                            ErrorStatisticsHandler.logError((Exception) target, getCurrentCommandString());
                        }
                    } else {
                        target.printStackTrace();
                    }
                } else if (e instanceof MyException) {
                    ((MyException) e).print();
                    ErrorStatisticsHandler.logError(e, getCurrentCommandString());
                } else {
                    e.printStackTrace();
                }
            }
        }
        scanner.close();
    }

    private void addUser() {
        int id = Integer.parseInt(commands[1]);
        int age = Integer.parseInt(commands[2]);
        String name = commands[3];
        try {
            network.addUser(id, name, age);
        } catch (EqualUserIdException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (InvalidAgeException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }

    private void uploadVideo() {
        int uploaderId = Integer.parseInt(commands[1]);
        int videoId = Integer.parseInt(commands[2]);
        
        try {
            network.uploadVideo(uploaderId, videoId);
        } catch (UserIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (EqualVideoIdException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }
    
    private void followUser() {
        int id1 = Integer.parseInt(commands[1]);
        int id2 = Integer.parseInt(commands[2]);
        try {
            network.followUser(id1, id2);
        } catch (UserIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (SelfSubscriptionException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (DuplicateSubscriptionException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }
    
    private void unfollowUser() {
        int id1 = Integer.parseInt(commands[1]);
        int id2 = Integer.parseInt(commands[2]);
        try {
            network.unfollowUser(id1, id2);
        } catch (UserIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (FollowLinkNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }
    
    private void watchVideo() {
        int userId = Integer.parseInt(commands[1]);
        int videoId = Integer.parseInt(commands[2]);
        try {
            network.watchVideo(userId, videoId);
        } catch (UserIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (VideoIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }
    
    private void queryReceivedUnwatchedVideos() {
        int userId = Integer.parseInt(commands[1]);
        try {
            List<Integer> videos = network.queryReceivedUnwatchedVideos(userId);
            System.out.println("query_received_unwatched_videos succeeded");
            if (videos.isEmpty()) {
                System.out.println("None");
            } else {
                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < videos.size(); i++) {
                    sb.append(videos.get(i));
                    if (i < videos.size() - 1) {
                        sb.append(" ");
                    }
                }
                System.out.println(sb);
            }
        } catch (UserIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }
    
    private void queryUpFollowersAgeRatio() {
        int upId = Integer.parseInt(commands[1]);
        try {
            double[] ratios = network.queryUpFollowersAgeRatio(upId);
            String name = network.getUser(upId).getName();
            
            System.out.println("query_up_followers_age_ratio succeeded");
            System.out.printf("%s %.2f %.2f %.2f %.2f\n",
                    name, ratios[0], ratios[1], ratios[2], ratios[3]);
        } catch (UserIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }
    
    private void queryMutualFollowingSum() {
        System.out.println(network.queryMutualFollowingSum());
    }
    
    private void queryShortestPath() {
        int id1 = Integer.parseInt(commands[1]);
        int id2 = Integer.parseInt(commands[2]);
        try {
            System.out.println(network.queryShortestPath(id1, id2));
        } catch (UserIdNotFoundException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        } catch (UncessException e) {
            e.print();
            ErrorStatisticsHandler.logError(e, getCurrentCommandString());
        }
    }
}