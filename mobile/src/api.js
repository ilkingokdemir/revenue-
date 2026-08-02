import axios from "axios";
import AsyncStorage from "@react-native-async-storage/async-storage";

export const DEFAULT_SERVER = "https://review-hub-108.preview.emergentagent.com";

const client = axios.create({ timeout: 20000 });

client.interceptors.request.use(async (config) => {
  const server = (await AsyncStorage.getItem("server_url")) || DEFAULT_SERVER;
  const token = await AsyncStorage.getItem("token");
  config.baseURL = `${server.replace(/\/$/, "")}/api`;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export const login = async (email, password) => {
  const { data } = await client.post("/auth/login", { email, password });
  const token = data.access_token || data.token;
  await AsyncStorage.setItem("token", token);
  return data;
};

export const logout = async () => AsyncStorage.removeItem("token");
export const getToken = () => AsyncStorage.getItem("token");
export default client;
